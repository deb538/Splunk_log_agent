# A2A over Amazon SQS: design, failure handling and operations

Reference implementation of a **custom A2A protocol binding** carried over SQS. Package: `a2a_sqs/`.
What was tested and what was not is stated in section 11. Read that before relying on any claim here.

## 1. Moving parts

```
 Agent A (caller)                                         Agent B (your agent)
 +------------------+   request queue (per agent)    +----------------------+
 | Caller           | -----------------------------> | Worker (N copies)    |
 |  send / stream   |                                |  claim, run handler, |
 |  reply pump      | <----------------------------- |  heartbeat, emit     |
 +--------+---------+   reply queue (per caller)     +----------+-----------+
          |                                                    |
   CallerStore (DynamoDB)                               TaskStore (DynamoDB)
   pending + replies by seq                             task record, lease, events
          |                                                    |
          +---------------- S3 payload bucket (> 200 KB) ------+
          request DLQ <- SQS redrive after maxReceiveCount; DlqNotifier tells the caller
```

SQS moves messages. **DynamoDB holds the truth** (who owns a task, which events exist). SQS is at-least-once and
unordered, so correctness rests on DynamoDB, not on SQS behaving.

## 2. Wire format

Body = the JSON-RPC 2.0 A2A payload (`method`, `params`; `id` = correlation id). Above 200 KB the body is replaced by
`{"a2a_sqs_ref": {bucket, key, sha256}}` (claim check); the receiver checks bucket and hash. SQS max is 1 MiB
(including attributes) and 10 attributes per message (we use 8).

| Request attribute | Meaning |
|---|---|
| `sender`, `correlation-id` | who, and the idempotency key (also the JSON-RPC `id`) |
| `reply-to` | caller's reply queue URL for this request's region |
| `deadline`, `sent-at` | epoch ms. The deadline is the caller's patience, and doubles as the replay window |
| `kid`, `sig` | HMAC-SHA256 over sender, correlation-id, reply-to, deadline, sent-at, sha256(body) |

Reply attributes: `sender`, `correlation-id`, `seq` (1, 2, 3 ...), `final` (`1` on the last event), `kid`, `sig`.
A reply body is one JSON-RPC message: `{"result": <A2A event>}` or `{"error": {...}}`. The final success event
is `{"result": null}`.

Error codes: standard JSON-RPC, plus **-32040** request expired, **-32041** retries exhausted, **-32042**
dead-lettered. Check these do not collide with codes in the A2A version you target. The spec requires a custom
binding to map every A2A error type, so write that mapping table for your binding.

## 3. Happy path, step by step

1. **Caller `send()`**: writes a `PENDING` record (deadline, method) to DynamoDB, *then* signs and enqueues. If the
   process dies in between, the intent is recorded and can be re-sent with the same correlation id.
2. **Worker receives** (long poll, up to `max_in_flight`). It verifies the signature **before parsing** anything,
   then checks `reply-to` against `allowed_reply_prefixes` and the sender against `allowed_senders`. Failures are
   deleted and counted (`rejected`). Nobody trustworthy exists to answer.
3. **Cheap rejections** are answered without creating task state: bad JSON (-32700), missing method (-32600),
   deadline already passed (-32040, the handler never runs).
4. **Claim**: conditional put on `(sender#correlation_id)` creates the task with a lease. Outcomes:
   `NEW`, `TAKEOVER` (lease expired or released), `DONE` (replay stored events, do not run), `BUSY` (a live worker
   has it; look again after its lease), `DEAD` (drop).
5. **Run**: the handler yields events. A heartbeat thread extends the SQS visibility timeout and the DynamoDB lease
   every `heartbeat_s`.
6. **Emit**, per event: assign `seq`, persist to DynamoDB in a transaction that is conditional on "I still own
   this task", *then* send to the caller's reply queue. Persist first means a crash can always be replayed.
7. **Finish**: the end marker is persisted in the same transaction that flips the task to `DONE`, then the request
   message is deleted. "Result saved" and "task finished" cannot disagree.
8. **Caller pump** validates the signature and sender, stores the reply **by seq** (conditional put, so duplicates
   are dropped), *then* deletes it from the reply queue. `stream()` reads the table, yields events in seq order,
   holds at gaps until the missing event arrives, and stops at the final event.

## 4. Retry policy

| Failure inside the handler | Behaviour |
|---|---|
| `A2AError(code, msg)` | Permanent. Caller gets the JSON-RPC error, message deleted, **no retry**. |
| `TransientError` or any other exception | Retry. Lease released, visibility set to jittered exponential backoff `uniform(base, min(cap, base*2^(n-1)))` where n = SQS receive count. Next receive is a `TAKEOVER`. |
| Receive count reaches `max_attempts` (default 5) | Caller gets **-32041** as a terminal event, the request is copied to the DLQ for forensics, the original is deleted. |
| Worker dies before any of that | Visibility expires, SQS redelivers. After `maxReceiveCount` (10 in the template) SQS moves it to the DLQ; the `DlqNotifier` then tells the caller **-32042**. |

Keep `max_attempts < maxReceiveCount`: the worker gives up first and says so itself; the SQS limit is the safety net
for poison messages that crash the process.

## 5. Failover scenarios

| Scenario | What happens |
|---|---|
| Worker crashes mid-task | Heartbeat stops, visibility and lease expire (about `visibility_s`). Another worker claims with `TAKEOVER`, re-publishes every stored event (the caller may have missed some), and runs the handler with `ctx.attempt` and `ctx.prior_events`. |
| Worker hangs (zombie), later wakes | Its next event write fails the ownership condition, so it raises `LeaseLost`, stops, counts `fenced`. It cannot append to or finish a task it no longer owns. |
| Deploy / SIGTERM | `Worker.stop(drain_s)` stops polling, waits for in-flight work, then sets visibility 0 and releases leases so peers resume at once instead of waiting out a timeout. |
| Duplicate request (client retry, SQS duplicate) | Same correlation id means one task. `BUSY` is deferred, `DONE` is replayed, never re-executed. |
| Duplicate or out-of-order replies | Caller dedupes by seq and reads in order. |
| Caller process dies | Pending record and replies are in DynamoDB. Any instance can `stream(corr)` later. |
| Reply-queue send fails | Treated as a transient error and retried; the takeover replays stored events. |
| SQS outage in one region | `Caller.send()` tries endpoints in order; a per-endpoint circuit breaker (3 failures, 30 s cooldown) moves the healthy endpoint first. Workers and the reply pump back off and keep retrying. |
| Every endpoint down | `SendFailed` is raised, nothing is silently dropped. |
| Caller's deadline passes | `stream()` raises `DeadlineExceeded` and marks `TIMEOUT`. Workers skip expired requests. |
| Poison message | Retries exhausted, or DLQ plus notifier. The caller is always told, never left waiting. |

### Multi-region
Deploy the template in two regions. Give the caller two `Endpoint`s (request queue and reply queue in each region).
Queue URLs carry the region, so one client set serves both. **Not built or tested:** DynamoDB global tables for
the task store. With separate per-region stores, a request sent to region 2 after region 1 *accepted* it may run
twice, so handlers must be idempotent on `ctx.correlation_id` (payments, emails, tickets).

## 6. Writing the handler

```python
def handler(request: dict, ctx: Context):
    for step in plan(request["params"]):
        ctx.check()                    # lease lost or deadline passed -> stops cleanly
        if ctx.cancelled():
            yield {"kind": "status-update", "state": "canceled"}; return
        yield do_step(step, idempotency_key=f"{ctx.correlation_id}:{step.id}")
```

* The transport guarantees each **sequence number** is stored once and only by the current owner. It does **not**
  guarantee the handler body runs once. Side effects need idempotency keys.
* A retried or taken-over handler starts from the top. Event numbering continues after the prior events, so a
  handler that ignores `ctx.prior_events` re-emits its early steps. Use `prior_events` to skip finished work.
* Calls that outlive the lease: the heartbeat extends it. `max_runtime_s` (11 h) stops extending before SQS's 12 h
  visibility cap. For work longer than that, split it into steps across messages.

## 7. Security

* **Signature before parse.** Tampered `reply-to` (redirecting answers) or swapped bodies are rejected.
* **Reply-to allow-list** (`allowed_reply_prefixes`) stops a validly signed request from pointing replies at an
  attacker's queue.
* **Deadline = replay window.** A captured request replayed after its deadline is answered -32040, not run.
* **Cancel scoping.** A cancel only matches the sender's own correlation ids.
* **KMS encryption** on queues, tables and bucket; **IAM** limits who can send to each queue; TLS enforced by
  queue policy.
* **Limitation:** HMAC with a shared keyring means *any holder of a key can sign as any sender id*, including as the
  agent. For production use asymmetric signatures (KMS `Sign`, or Ed25519) behind the same `Keyring` interface, one
  key per party. Rotate by adding the new key everywhere, switching `active`, then removing the old one.

## 8. Tuning

| Setting | Default | Guidance |
|---|---|---|
| `visibility_s` (queue + worker) | 60 | Time to notice a dead worker. Lower = faster failover, more heartbeat calls. |
| `heartbeat_s` | 20 | About a third of `visibility_s`, so two missed beats still do not expire it. |
| `max_attempts` | 5 | Below the redrive `maxReceiveCount` (10). |
| `backoff_base_s` / `cap` | 5 / 300 | Match your downstream's recovery time. |
| `max_in_flight` | 4 | Concurrent tasks per worker process. Scale out workers, not just threads. |
| Request retention | 4 days | Must exceed the longest deadline you allow. Bucket lifecycle (7 d) must exceed it too. |
| Record TTL | 7 days | After this, a late duplicate looks new; the expired deadline still blocks it. |

Scale workers on `ApproximateAgeOfOldestMessage` (the template alarms at 5 minutes), not on depth.

## 9. Operations runbook

* **DLQ alarm fires.** Run `DlqNotifier.poll_once()` (or wire it to the DLQ as a Lambda). It tells callers once and
  parks the message for 12 h. Inspect, fix the cause.
* **Redrive does not re-run a dead task.** A redriven message carries the original correlation id; its task is
  `DEAD`/`DONE`, so the worker drops it. To retry, the caller sends a **new** correlation id.
* **Rotate keys**, per section 7.
* **Watch** the counters on `Worker.metrics` / `Caller.metrics`: `retried`, `takeover`, `fenced`, `rejected`,
  `exhausted`, `failovers`, `duplicate_replies`. A rising `fenced` means heartbeats are too slow or workers are
  starved. A rising `rejected` means misconfigured keys or a hostile sender.

## 10. Known gaps (decide before production)

1. **No acknowledgement or resend.** Failover happens when *sending* fails. If a region accepts the message but has
   no live workers, the caller waits until its deadline. Fix: resend the same correlation id to the other endpoint
   after N seconds without a first event (safe, the agent deduplicates).
2. **Event size.** Each event is stored whole in a DynamoDB item (400 KB limit). Keep events under about 300 KB and
   put large artifacts in S3, yielding a URL. Oversize events fail as a transient error, then exhaust retries.
3. **FIFO queues** are supported by the argument plumbing but untested. FIFO group blocking means one retrying
   message stalls its whole group. Standard queues plus the idempotency store are the default recommendation.
4. **A2A semantics are yours.** This layer carries opaque JSON-RPC bodies. It does not implement `tasks/get`,
   push notifications or the Agent Card; wire `handler` to the SDK's request handler for that.
5. The shared-key limitation in section 7.

## 11. What was and was not verified

* **Verified:** 20 tests against in-memory fakes pass (happy path, streaming order, duplicates, replay, transient and
  permanent errors, retry exhaustion plus DLQ, stalled-worker takeover with zombie fencing, graceful drain,
  region failover and breaker, caller restart, DLQ notifier exactly-once, expiry, deadline, cancel, out-of-order
  and duplicate replies, forged requests and replies, S3 claim check). The local demo runs.
* **Not verified:** anything against real AWS. `boto3` and `moto` could not be installed in the build environment
  (no PyPI access), so `common.Aws` and the real DynamoDB/SQS expression handling are untested. The fakes were made
  strict about DynamoDB's expression rules, but real behaviour wins. The CloudFormation template parses but was
  not linted or deployed. Nothing was load-tested. FIFO behaviour and DynamoDB global tables were not exercised.
* **First steps before production:** run the suite against LocalStack or a real sandbox account, `cfn-lint` the
  template, load-test with your real handler.
