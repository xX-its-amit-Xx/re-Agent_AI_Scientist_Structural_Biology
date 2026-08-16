---
name: onboarding
description: >-
  The front door. Ask the user for the credentials this run needs without ever seeing their
  values, walk them through any interactive sign-in, discover what compute they have — local,
  SSH cluster, serverless, hosted notebook — decide where hot and cold data live, work out how
  many subprocesses this machine can sustain, and refuse to declare the system ready until the
  problem and its data are present. Produces the capability registry every later stage binds
  against. Use at the start of a project, when a run fails for want of a credential, or when
  deciding where something should execute. Trigger on: "set up", "get started", "API keys",
  "credentials", "which compute", "where should this run", "out of disk", "how many workers",
  "onboard", or /onboarding.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# Onboarding

Before the pipeline can attack a problem it needs credentials, compute, somewhere to put data,
and a realistic idea of what this machine can run. `reagent init` does the mechanical part:

```bash
reagent init --hot C:/Temp --cold O:/rclone-offload --cold-is-network
```

It probes CPUs and free space, writes `.env.template`, and prints what is blocking.

## The secret rule, and its honest limit

**The agent writes the names. The user fills the values. The agent never sees them.**

That is the only measure here that is *structural* rather than a mitigation, so it is the one the
design leans on. A secret that never enters the agent's context cannot be exfiltrated from it.

Everything else is defence in depth, and it is worth being precise about what each buys:

| Measure | Prevents |
|---|---|
| agent writes template only, user fills `.env` | the value entering the agent's context at all |
| pass by **name**, never interpolate into a command line | exposure via process listings, shell history, echoed invocations |
| a credential-request tool where one exists | the agent handling the value even in transit |
| deny-list `.env` in the agent's tool permissions | an accidental read |
| gitignore plus a CI check | the irreversible failure — a pushed credential is public and must be rotated, not deleted |
| `redact()` on any display | a value reaching a log or a transcript |

**And the limit, stated plainly because the alternative is a false assurance:** an agent with
file-read and shell access can read `.env`. No file permission changes that while it runs as the
same user. The deny rule prevents an accident, not an intent. `SecretVault.problems()` says so
rather than reporting the deny rule as protection.

Three consequences for how this skill behaves:

- **Never ask the user to paste a key into the chat.** It would enter the transcript, and a
  credential in a transcript has to be rotated. Point at the template.
- **Ask for the narrowest scope that works** — read-only, single-project, workspace-scoped. Free
  at setup time, and it bounds the damage of any leak. `scope_note` records it and its absence is
  flagged.
- **`SecretSpec` has no `value` field**, and `SecretVault` rejects text that looks like a real
  credential. If a value ever appears in one of these objects the model is being used wrongly.

## Everything is optional, and the pipeline degrades

Every default secret is `optional=True`, because with no compute credentials Stages 0–2 still run
end to end and that is a useful system. Mark one required only when a stage genuinely cannot
proceed.

What blocks is narrower than what is missing: **a required secret, an incomplete sign-in, no
problem, and no data.** Storage and compute are not blocking — local-only with no cold mount is a
legitimate configuration that limits what can run, and the right response is to record the limit
so a later stage does not plan a GPU run against nothing.

## Interactive sign-ins

`AuthFlow` models what the agent *cannot* do. OAuth and device-code flows need a browser and a
human decision, so the agent's job is to name the command, explain it, and verify the result —
never to handle the token.

Show the command with the `!` prefix so it runs in the user's own session:

```
! modal token new
```

Then verify with a cheap read-only call. An unverified sign-in is a plan.

## Compute: match the target to the run's shape

`ComputeTarget.suits_long_runs` is the property that matters, and it is about timeouts rather
than GPUs:

| Kind | Good for | The trap |
|---|---|---|
| local | everything in Stages 0–2, and orchestration | no GPU; the working disk is usually the constraint |
| SSH cluster (Slurm) | long unattended GPU work | **never run work on the login node** — request through the scheduler |
| serverless | batch GPU jobs from code | metered; cold starts |
| hosted notebook | interactive GPU work | **idle *and* total timeouts** — a large GPU that dies mid-run |
| managed API | one-off inference | opaque versioning |

A hosted notebook with a big GPU is worse than a modest scheduler allocation for anything
unattended, and that is counter-intuitive enough to be worth stating. `problems()` flags an
environment with no verified target suited to a long run.

**`verified` means a trivial job actually completed there.** Not that credentials exist. This
project has been bitten three times by tooling that installs and does not run — ChimeraX
offscreen is Linux-only, PLIP crashes with the pip openbabel wheel, ProLIF segfaults from stdin —
so an unverified binding is a plan and is labelled as one.

## Storage: hot work local, cold archive remote

Three tiers, and the rule that matters is about *latency*, not size:

- **hot** — scratch and anything in a compute loop. Must be local. A network mount here makes an
  I/O problem look like a model problem, which is an expensive confusion.
- **working** — the repo and current artifacts.
- **cold** — archive, finished runs, large inputs read occasionally. A network mount is correct
  here, and terabytes of it are better than gigabytes of local.

`lazy_fetch` is on by default: the graph already stores a `DataRef` pointer, so materialising
everything up front is a choice rather than a requirement.

**Check the working disk before planning anything.** On this machine `reagent init` reports the
working volume with **about 1 GB free**, which is not enough for a run that writes structures —
so offloading to cold storage is a precondition here, not an optimisation.

## Subprocesses: RAM is usually the binding constraint

```
workers = min(cpus - reserve, floor((available_ram - reserve) / per_worker_ram), cap)
```

`binding_constraint()` says which term won. Oversubscribing RAM is worse than oversubscribing
CPU: too many processes on too few cores is merely slow, while too many for the memory triggers
the OOM killer or swap, **which presents as a hang** and is much harder to diagnose.

`per_worker_ram_gb` should be measured from one run, not guessed. An overestimate silently
serialises the whole pipeline — `problems()` flags concurrency collapsing to 1 on a many-core
machine for exactly that reason. `probe_resources()` deliberately assumes a low 2 GB per core,
because guessing high produces the hang and guessing low only costs throughput.

## Downloads

Lazy, resumable, checksummed, concurrency-capped, landing on cold storage. Two of those are not
optional:

- **Checksums.** A truncated download produces a file that parses and is wrong, which is the
  worst available failure mode — nothing downstream detects it.
- **Resumability.** A 310 MB fetch that cannot resume will be restarted from zero on any
  interruption.

## Then start

`Onboarding.ready()` is a gate, not a report. A run that starts without a capability it needs
does not fail — **it silently produces a smaller answer**, and nothing downstream distinguishes
that from the problem being easy. So the blocking list is short and hard: required secrets,
completed sign-ins, a `ProblemSpec`, and declared data.

Once ready, hand `tools.registry` to Stage 4 and the compute targets to Stage 3, and start at
`ai-scientist`.

## Anti-patterns

- **Asking for a key in the chat.** It lands in the transcript and must then be rotated.
- **Reporting the deny rule as protection.** It prevents an accident. Say that.
- **Requesting an account-wide token because it is one click fewer.**
- **Declaring a compute target verified because the credential resolved.**
- **Putting scratch on the network mount** because it has the most free space. It has the most
  space because it is the slowest.
- **Guessing `per_worker_ram_gb` high to be safe.** That is the direction that hangs.
- **Starting anyway.** The gate exists because the failure is silent.
