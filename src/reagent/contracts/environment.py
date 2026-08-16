"""Onboarding: credentials, compute, storage, and the gate before work starts.

The front door. Before the pipeline can attack a problem it needs API keys, possibly an OAuth
flow, whatever compute the user has, somewhere to put data, and a sane idea of how many
subprocesses this machine can run. This module models all of that and, importantly, **refuses to
declare the system ready when a required piece is missing** — a run that starts without a
capability it needs does not fail, it silently produces a smaller answer.

Secrets, and an honest limit
----------------------------
The requirement is that credentials live in ``.env`` and are safe from agent exfiltration. The
first half is easy. The second half **cannot be fully guaranteed, and saying otherwise would be
the most dangerous sentence in this file.** An agent with file-read and shell access can read
``.env``; no file permission changes that while the agent runs as the same user.

What actually reduces exposure, in descending order of effectiveness:

1. **The agent never sees the value.** It writes a *template* of names with empty values and the
   user fills them in through a channel the agent does not observe. A secret that never enters
   the agent's context cannot be exfiltrated from it, and this is the only measure that is
   structural rather than a mitigation.
2. **Subprocesses inherit from the environment.** The value is passed by *name*, never
   interpolated into a command line — a command line is visible in process listings, shell
   history, and any log that echoes the invocation.
3. **A credential-request tool where one exists**, so a password manager supplies the value
   directly and the agent handles only the name.
4. **Deny-list ``.env`` in the agent's own tool permissions**, gitignore it, and check for it in
   CI. Defence in depth: each of these is bypassable, and together they mean an accident is
   unlikely even though an intent is not preventable.
5. **Redact on the way out.** ``redact()`` here, and never echo the environment.

``SecretSpec`` therefore carries a name and never a value, and ``SecretVault`` is a registry of
*names and status*. If a value ever appears in one of these objects, the model is being used
wrongly — hence the validator that rejects anything that looks like a populated secret.

Resources
---------
The subprocess and download policies are grounded in what this machine actually is rather than
in a general heuristic: ``D:`` runs near-full, ``C:\\Temp`` has room and is fast, and ``O:``
is network-backed cloud storage with terabytes free and latency that makes it wrong for anything
in a compute loop. So the storage tiers are explicit and the rule is *hot work local, cold
archive remote* — putting a training loop's scratch on a network mount is the single easiest way
to make a run look like a model problem when it is an I/O problem.
"""

from __future__ import annotations

import os
import re
import shutil
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

#: Patterns that look like a real credential rather than a placeholder. Used to reject a value
#: that has leaked into a contract object, which is the failure this module most wants to avoid.
_LOOKS_SECRET = re.compile(
    r"^(?:sk-|pk-|ghp_|gho_|github_pat_|xox[baprs]-|AKIA|ASIA|AIza|ya29\.)"
    r"|^[A-Za-z0-9_\-]{32,}$"
)


def redact(text: str, *, keep: int = 4) -> str:
    """Mask a credential for display. Never log an unredacted one.

    Keeps a short suffix so a user can tell *which* key it is without the value being usable.
    """
    t = (text or "").strip()
    if len(t) <= keep:
        return "*" * len(t)
    return "*" * (len(t) - keep) + t[-keep:]


class SecretStatus(str, Enum):
    MISSING = "missing"
    PRESENT = "present"          # the name resolves to a non-empty value in the environment
    PLACEHOLDER = "placeholder"  # present but still the template's dummy text
    INVALID = "invalid"          # present and rejected by the service


class SecretSpec(BaseModel):
    """One credential, by **name only**.

    There is deliberately no ``value`` field. The agent writes the template, the user fills it,
    and the value reaches a subprocess through the environment — so it never enters the agent's
    context and cannot be exfiltrated from it.
    """

    name: str = Field(..., description="Environment variable name, e.g. 'MODAL_TOKEN_SECRET'.")
    purpose: str = Field(
        ..., min_length=10, description="What breaks without it, in one line."
    )
    obtain_from: str = Field(
        ..., description="Where the user gets it — a URL or a CLI command they run themselves."
    )
    required_for: list[str] = Field(
        default_factory=list,
        description="Capabilities that need it. Empty means it is optional everywhere.",
    )
    optional: bool = Field(
        default=True,
        description=(
            "Whether the system can run without it. Optional is the default because most "
            "compute here is optional — the pipeline should degrade rather than refuse."
        ),
    )
    scope_note: str | None = Field(
        default=None,
        description=(
            "The narrowest scope that works. A read-only or single-project token limits the "
            "damage of any leak, and asking for it is free at setup time."
        ),
    )

    @field_validator("name")
    @classmethod
    def _looks_like_an_env_name(cls, v: str) -> str:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", v):
            raise ValueError(
                f"secret name {v!r} should be an UPPER_SNAKE environment variable name. This "
                "field holds a name, never a value."
            )
        return v

    def status(self, env: dict[str, str] | None = None) -> SecretStatus:
        """Resolve from the environment without returning the value."""
        src = env if env is not None else os.environ
        raw = (src.get(self.name) or "").strip()
        if not raw:
            return SecretStatus.MISSING
        if raw.lower() in {"changeme", "todo", "xxx", "your-key-here", "replace-me", "..."}:
            return SecretStatus.PLACEHOLDER
        return SecretStatus.PRESENT


class SecretVault(BaseModel):
    """The declared credentials and their status. Names and status only, never values."""

    specs: list[SecretSpec] = Field(default_factory=list)
    env_path: str = Field(default=".env", description="Where values live. Must be gitignored.")
    template_path: str = Field(default=".env.template")
    gitignored: bool = Field(
        default=True, description="Whether env_path is gitignored. Checked, not assumed."
    )
    agent_read_denied: bool = Field(
        default=False,
        description=(
            "Whether the agent's own tool permissions deny reading env_path. Worth doing and "
            "worth being honest about: it prevents an accident, not an intent, because an agent "
            "with shell access has other paths to the same bytes."
        ),
    )

    @model_validator(mode="after")
    def _no_values_here(self) -> SecretVault:
        """Reject anything that looks like a credential having leaked into this object."""
        for s in self.specs:
            for field, text in (("purpose", s.purpose), ("obtain_from", s.obtain_from),
                                ("scope_note", s.scope_note or "")):
                for token in text.split():
                    if _LOOKS_SECRET.match(token) and len(token) >= 20:
                        raise ValueError(
                            f"secret {s.name}: {field} contains {redact(token)}, which looks "
                            "like an actual credential. This model holds names and status only "
                            "— a value here would be committed, logged, and in the agent's "
                            "context."
                        )
        return self

    def resolve(self, env: dict[str, str] | None = None) -> dict[str, SecretStatus]:
        return {s.name: s.status(env) for s in self.specs}

    def missing_required(self, env: dict[str, str] | None = None) -> list[str]:
        return [
            s.name for s in self.specs
            if not s.optional and s.status(env) is not SecretStatus.PRESENT
        ]

    def problems(self, env: dict[str, str] | None = None) -> list[str]:
        out: list[str] = []
        if not self.gitignored:
            out.append(
                f"{self.env_path} is not gitignored. This is the one failure here that is "
                "irreversible: a committed and pushed credential is public and must be rotated, "
                "not deleted."
            )
        if missing := self.missing_required(env):
            out.append(f"required secrets missing or placeholder: {missing}")
        placeholders = [
            s.name for s in self.specs if s.status(env) is SecretStatus.PLACEHOLDER
        ]
        if placeholders:
            out.append(
                f"still template text: {placeholders}. A placeholder reads as present and fails "
                "at the first call, usually far from here."
            )
        if not self.agent_read_denied:
            out.append(
                f"the agent's tool permissions do not deny reading {self.env_path}. Adding the "
                "deny rule prevents an accidental read; note it does not prevent a determined "
                "one, because shell access reaches the same bytes."
            )
        broad = [s.name for s in self.specs if not s.scope_note]
        if broad:
            out.append(
                f"no scope recorded for {broad}. Ask for the narrowest token that works — "
                "read-only, single-project — since it is free at setup and limits any leak."
            )
        return out

    def template(self) -> str:
        """The file the agent writes: names, comments, and empty values."""
        lines = [
            "# Credentials for this project. Values are yours; this file is gitignored.",
            "#",
            "# The agent wrote the NAMES. It should never see the VALUES: fill them in yourself,",
            "# and prefer the narrowest scope each service offers.",
            "",
        ]
        for s in sorted(self.specs, key=lambda x: (x.optional, x.name)):
            lines.append(f"# {s.purpose}")
            lines.append(f"#   obtain: {s.obtain_from}")
            if s.scope_note:
                lines.append(f"#   scope:  {s.scope_note}")
            lines.append(f"#   {'required' if not s.optional else 'optional'}"
                         + (f" for {', '.join(s.required_for)}" if s.required_for else ""))
            lines.append(f"{s.name}=")
            lines.append("")
        return "\n".join(lines)


class AuthFlow(BaseModel):
    """An interactive sign-in the agent can prepare but must not complete.

    OAuth and device-code flows need a browser and a human decision. The agent's job is to run
    the command that starts the flow, tell the user exactly what to do, and then verify the
    result — not to handle the token.
    """

    service: str
    kind: str = Field(default="oauth", description="'oauth', 'device_code', or 'cli_login'.")
    start_command: str = Field(
        ..., description="What the user runs, e.g. 'modal token new'. They run it, not the agent."
    )
    verify_command: str | None = Field(
        default=None, description="A cheap read-only call that proves it worked."
    )
    completed: bool = False
    note: str | None = None

    @property
    def instruction(self) -> str:
        """What to show the user. The `!` prefix runs it in their session, not the agent's."""
        return (
            f"Run this yourself so the agent never handles the token:\n"
            f"    ! {self.start_command}\n"
            + (f"Then verify with:\n    ! {self.verify_command}\n"
               if self.verify_command else "")
        )


# ---------------------------------------------------------------------------
# Compute and storage
# ---------------------------------------------------------------------------


class ComputeKind(str, Enum):
    LOCAL = "local"
    SSH_CLUSTER = "ssh_cluster"      # Slurm login node; jobs go through the scheduler
    SERVERLESS = "serverless"        # Modal and similar
    HOSTED_NOTEBOOK = "hosted_notebook"  # Colab, Kaggle, molab — idle timeouts
    MANAGED_API = "managed_api"      # a vendor endpoint that runs the model for you


class ComputeTarget(BaseModel):
    """One place work can run, and what it is good and bad at."""

    name: str
    kind: ComputeKind
    reachable_via: str | None = Field(
        default=None, description="'ssh explorer', a CLI, or an endpoint."
    )
    gpu: str | None = None
    cpus: int | None = Field(default=None, gt=0)
    ram_gb: float | None = Field(default=None, gt=0)
    max_walltime_h: float | None = Field(
        default=None, gt=0,
        description=(
            "Hard limit. Hosted notebooks have idle *and* total timeouts, which is why a long "
            "uninterrupted run belongs on a scheduler or a serverless platform."
        ),
    )
    idle_timeout_min: float | None = Field(
        default=None, gt=0, description="Set for hosted notebooks; the thing that kills long runs."
    )
    metered: bool = False
    requires_secret: list[str] = Field(default_factory=list)
    scheduler: str | None = Field(
        default=None, description="'slurm' means never run work on the login node."
    )
    verified: bool = Field(
        default=False, description="Has a trivial job actually completed here?"
    )

    @property
    def suits_long_runs(self) -> bool:
        return self.idle_timeout_min is None and (
            self.max_walltime_h is None or self.max_walltime_h >= 6
        )

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.verified:
            out.append(f"{self.name}: never verified with a trivial job")
        if self.scheduler == "slurm" and self.kind is ComputeKind.SSH_CLUSTER:
            out.append(
                f"{self.name}: Slurm target — request resources through the scheduler and run "
                "nothing heavy on the login node"
            )
        if self.idle_timeout_min:
            out.append(
                f"{self.name}: idle timeout {self.idle_timeout_min:.0f} min, so it is unsuitable "
                "for an unattended long run however large its GPU is"
            )
        return out


class StorageTier(str, Enum):
    HOT = "hot"          # scratch and anything in a compute loop
    WORKING = "working"  # the repo and current artifacts
    COLD = "cold"        # archive, finished runs, large inputs read occasionally


class StorageMount(BaseModel):
    """A place to put bytes, with the property that decides what belongs there."""

    path: str
    tier: StorageTier
    free_gb: float | None = Field(default=None, ge=0)
    network_backed: bool = Field(
        default=False,
        description=(
            "Whether it is cloud- or network-backed. Decisive: a network mount is wrong for "
            "anything in a compute loop, and putting scratch there makes an I/O problem look "
            "like a model problem."
        ),
    )
    note: str | None = None

    @property
    def suits_hot_io(self) -> bool:
        return not self.network_backed and (self.free_gb or 0) >= 5


class StoragePlan(BaseModel):
    """Where each kind of data goes, and how much room there actually is."""

    mounts: list[StorageMount] = Field(default_factory=list)
    lazy_fetch: bool = Field(
        default=True,
        description=(
            "Fetch dataset bytes on demand rather than up front. The graph already stores the "
            "pointer as a DataRef, so materialising everything is a choice rather than a "
            "requirement."
        ),
    )
    min_free_gb: float = Field(
        default=10.0, gt=0, description="Refuse to start a run below this on the hot mount."
    )

    def tier(self, tier: StorageTier) -> StorageMount | None:
        return next((m for m in self.mounts if m.tier is tier), None)

    def problems(self) -> list[str]:
        out: list[str] = []
        hot = self.tier(StorageTier.HOT)
        if hot is None:
            out.append("no hot mount declared — scratch will land wherever the cwd happens to be")
        elif hot.network_backed:
            out.append(
                f"hot mount {hot.path} is network-backed. Anything latency-sensitive belongs on "
                "local disk; this configuration will look like a slow model."
            )
        elif (hot.free_gb or 0) < self.min_free_gb:
            out.append(
                f"hot mount {hot.path} has {hot.free_gb:.1f} GB free against a {self.min_free_gb:.0f} "
                "GB floor. A run that fills the disk fails late and leaves partial artifacts."
            )
        if self.tier(StorageTier.COLD) is None:
            out.append(
                "no cold mount — finished runs and large inputs will accumulate on the working "
                "disk until something fails for lack of space"
            )
        return out


class ResourceBudget(BaseModel):
    """How much of this machine a run may use, and how many workers that implies.

    ``workers()`` is the number that matters. Oversubscribing RAM is worse than oversubscribing
    CPU: too many processes on too few cores is slow, and too many processes for the memory
    triggers the OOM killer or swap, which looks like a hang.
    """

    total_cpus: int = Field(..., gt=0)
    available_ram_gb: float = Field(..., gt=0)
    reserve_cpus: int = Field(
        default=2, ge=0, description="Left for the OS and the agent itself."
    )
    reserve_ram_gb: float = Field(default=4.0, ge=0)
    per_worker_ram_gb: float = Field(
        default=2.0, gt=0,
        description="Measured, not guessed. Structure work and MSA searches are memory-hungry.",
    )
    max_workers: int | None = Field(
        default=None, description="Hard cap, e.g. an API rate limit or a licence."
    )

    def workers(self) -> int:
        """Concurrency this machine can actually sustain. Never returns zero."""
        by_cpu = max(1, self.total_cpus - self.reserve_cpus)
        usable_ram = max(0.0, self.available_ram_gb - self.reserve_ram_gb)
        by_ram = max(1, int(usable_ram // self.per_worker_ram_gb))
        n = min(by_cpu, by_ram)
        if self.max_workers:
            n = min(n, self.max_workers)
        return max(1, n)

    def binding_constraint(self) -> str:
        by_cpu = max(1, self.total_cpus - self.reserve_cpus)
        by_ram = max(1, int(max(0.0, self.available_ram_gb - self.reserve_ram_gb)
                            // self.per_worker_ram_gb))
        if self.max_workers and self.max_workers <= min(by_cpu, by_ram):
            return "explicit cap"
        return "ram" if by_ram < by_cpu else "cpu"

    def problems(self) -> list[str]:
        out: list[str] = []
        if self.workers() == 1 and self.total_cpus > 4:
            out.append(
                f"concurrency collapses to 1 on {self.total_cpus} CPUs, limited by "
                f"{self.binding_constraint()}. Check `per_worker_ram_gb` is measured rather than "
                "a guess — an overestimate silently serialises the whole run."
            )
        if self.available_ram_gb - self.reserve_ram_gb < self.per_worker_ram_gb:
            out.append(
                "not enough free RAM for one worker at the declared per-worker figure; the run "
                "will swap or be killed"
            )
        return out


class DownloadPolicy(BaseModel):
    """How to bring bytes in without filling the disk or saturating the link."""

    lazy: bool = Field(default=True, description="Fetch on first use, not up front.")
    resumable: bool = Field(
        default=True,
        description="Range requests. A 310 MB download that cannot resume will be restarted.",
    )
    verify_checksum: bool = Field(default=True)
    max_concurrent: int = Field(default=3, gt=0)
    max_bytes: int | None = Field(
        default=None, description="Refuse a fetch above this without an explicit decision."
    )
    destination_tier: StorageTier = StorageTier.COLD
    bandwidth_note: str | None = None

    def problems(self) -> list[str]:
        out: list[str] = []
        if not self.verify_checksum:
            out.append(
                "checksums disabled — a truncated download produces a file that parses and is "
                "wrong, which is the worst available failure mode"
            )
        if not self.resumable:
            out.append("non-resumable downloads will be restarted from zero on any interruption")
        if self.destination_tier is StorageTier.HOT:
            out.append(
                "downloads are landing on the hot mount, which is the smallest one. Large inputs "
                "belong on cold storage with a lazy fetch into hot when needed."
            )
        return out


def probe_resources(hot_path: str = ".") -> ResourceBudget:
    """Read the machine's actual CPU and disk. RAM needs a dependency, so it is estimated.

    Deliberately conservative: guessing high on available RAM produces oversubscription, which
    manifests as a hang rather than an error, and is much harder to diagnose than being slow.
    """
    cpus = os.cpu_count() or 2
    # No psutil dependency, so RAM is inferred rather than read: assume 2 GB usable per core,
    # which is low for a workstation and therefore safe. Override with a measured figure when
    # one is available — an overestimate here serialises nothing and an underestimate only
    # costs throughput, while the reverse triggers the OOM killer and looks like a hang.
    ram_guess = max(4.0, cpus * 2.0)
    return ResourceBudget(
        total_cpus=cpus, available_ram_gb=ram_guess, per_worker_ram_gb=2.0,
    )


def probe_free_gb(path: str) -> float | None:
    """Free space on the volume holding ``path``, or None if it cannot be read."""
    try:
        return shutil.disk_usage(path).free / 1024**3
    except OSError:
        return None


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------


class OnboardingStep(str, Enum):
    SECRETS = "secrets"
    AUTH = "auth"
    COMPUTE = "compute"
    STORAGE = "storage"
    RESOURCES = "resources"
    PROBLEM = "problem"
    DATA = "data"

    @property
    def question(self) -> str:
        return {
            "secrets": "Which credentials does this run need, and are they present?",
            "auth": "Which interactive sign-ins must the user complete?",
            "compute": "Where can work run, and has each target been verified?",
            "storage": "Where do hot, working and cold data go?",
            "resources": "How many subprocesses can this machine sustain?",
            "problem": "What is the problem, in a validated ProblemSpec?",
            "data": "What training and test data exists, and where?",
        }[self.value]


class Onboarding(BaseModel):
    """Everything that must be true before the pipeline attacks the problem.

    ``ready()`` is a gate rather than a report. A run that starts without a capability it needs
    does not fail — it silently produces a smaller answer, and nothing downstream distinguishes
    that from the problem being easy.
    """

    vault: SecretVault = Field(default_factory=SecretVault)
    auth_flows: list[AuthFlow] = Field(default_factory=list)
    compute: list[ComputeTarget] = Field(default_factory=list)
    storage: StoragePlan = Field(default_factory=StoragePlan)
    resources: ResourceBudget | None = None
    downloads: DownloadPolicy = Field(default_factory=DownloadPolicy)
    problem_spec_path: str | None = None
    data_refs: list[str] = Field(
        default_factory=list, description="Dataset node ids or paths for training and test data."
    )

    def completed_steps(self, env: dict[str, str] | None = None) -> set[OnboardingStep]:
        done: set[OnboardingStep] = set()
        if self.vault.specs and not self.vault.missing_required(env):
            done.add(OnboardingStep.SECRETS)
        if all(f.completed for f in self.auth_flows):
            done.add(OnboardingStep.AUTH)
        if any(c.verified for c in self.compute):
            done.add(OnboardingStep.COMPUTE)
        if self.storage.mounts and not self.storage.problems():
            done.add(OnboardingStep.STORAGE)
        if self.resources is not None:
            done.add(OnboardingStep.RESOURCES)
        if self.problem_spec_path:
            done.add(OnboardingStep.PROBLEM)
        if self.data_refs:
            done.add(OnboardingStep.DATA)
        return done

    def blocking(self, env: dict[str, str] | None = None) -> list[str]:
        """Steps that must be done before any work starts.

        Storage and compute are *not* blocking: local-only with no cold mount is a legitimate
        configuration that limits what can run, and the right response is to record the limit
        rather than refuse. What blocks is a missing required secret, an incomplete sign-in, no
        problem, and no data — without those there is nothing to attack.
        """
        done = self.completed_steps(env)
        block: list[str] = []
        if OnboardingStep.SECRETS not in done and self.vault.missing_required(env):
            block.append(f"required secrets: {self.vault.missing_required(env)}")
        if pending := [f.service for f in self.auth_flows if not f.completed]:
            block.append(f"sign-in not completed: {pending}")
        if OnboardingStep.PROBLEM not in done:
            block.append("no ProblemSpec — nothing to attack")
        if OnboardingStep.DATA not in done:
            block.append("no training or test data declared")
        return block

    def ready(self, env: dict[str, str] | None = None) -> bool:
        return not self.blocking(env)

    def capabilities(self) -> list[str]:
        """What this environment can actually do, for the tool registry to bind against."""
        out: list[str] = []
        for c in self.compute:
            if c.verified:
                out.append(f"{c.kind.value}:{c.name}")
        return out

    def problems(self, env: dict[str, str] | None = None) -> list[str]:
        out: list[str] = []
        out += [f"secrets: {p}" for p in self.vault.problems(env)]
        out += [f"storage: {p}" for p in self.storage.problems()]
        out += [f"downloads: {p}" for p in self.downloads.problems()]
        if self.resources:
            out += [f"resources: {p}" for p in self.resources.problems()]
        for c in self.compute:
            out += [f"compute: {p}" for p in c.problems()]
        if not self.compute:
            out.append(
                "no compute target declared, so everything runs locally. A legitimate "
                "configuration — record it as a limitation so a later stage does not plan a GPU "
                "run against nothing."
            )
        elif not any(c.suits_long_runs and c.verified for c in self.compute):
            out.append(
                "no verified target suits a long unattended run. Hosted notebooks have idle "
                "timeouts; a scheduler or serverless platform is what survives one."
            )
        return out

    def summary(self, env: dict[str, str] | None = None) -> str:
        done = self.completed_steps(env)
        lines = ["Onboarding"]
        for step in OnboardingStep:
            mark = "x" if step in done else " "
            lines.append(f"  [{mark}] {step.value:10} {step.question}")
        if self.vault.specs:
            res = self.vault.resolve(env)
            lines.append("  secrets: " + ", ".join(f"{k}={v.value}" for k, v in res.items()))
        if self.resources:
            lines.append(
                f"  workers: {self.resources.workers()} "
                f"(limited by {self.resources.binding_constraint()})"
            )
        for m in self.storage.mounts:
            lines.append(
                f"  {m.tier.value:8} {m.path}"
                + (f"  {m.free_gb:.0f} GB free" if m.free_gb is not None else "")
                + ("  [network-backed]" if m.network_backed else "")
            )
        if block := self.blocking(env):
            lines.append("  BLOCKING:")
            lines += [f"    - {b}" for b in block]
        else:
            lines.append("  ready to start")
        if probs := self.problems(env):
            lines.append("  problems:")
            lines += [f"    - {p}" for p in probs]
        return "\n".join(lines)
