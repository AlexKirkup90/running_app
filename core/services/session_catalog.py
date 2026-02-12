"""Daniels-informed session catalog with prescriptive interval structures.

Each workout type specifies:
- Daniels pace labels (E, M, T, I, R) instead of generic zones
- Prescriptive interval blocks with reps, work/recovery durations
- Workout-specific progression and regression rules
- Phase affinity (which periodization phases favour this session)

This module is the single source of truth for all session type definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntervalBlock:
    """A single interval set within a main_set block."""
    reps: int
    work_duration_min: float
    work_pace: str          # Daniels label: E, M, T, I, R
    recovery_duration_min: float
    recovery_pace: str      # Usually E or "jog"
    description: str = ""


@dataclass(frozen=True)
class ProgressionRule:
    """Quantified rule for increasing workout difficulty."""
    trigger: str            # e.g. "readiness >= 3.5 for 2 consecutive sessions"
    action: str             # e.g. "+1 rep"
    guard: str = ""         # e.g. "ACR <= 1.2"


@dataclass(frozen=True)
class RegressionRule:
    """Quantified rule for reducing workout difficulty."""
    trigger: str
    action: str
    fallback_type: str = "" # e.g. "Easy Run" — swap to this if severe


@dataclass
class WorkoutType:
    """Complete definition of a Daniels-informed workout type."""
    name: str
    category: str           # broad grouping for UI/filtering
    intent: str
    energy_system: str
    daniels_pace: str       # primary Daniels pace: E, M, T, I, R
    phase_affinity: list[str]  # which phases prefer this session
    rpe_range: tuple[int, int]
    intervals: list[IntervalBlock] = field(default_factory=list)
    progressions: list[ProgressionRule] = field(default_factory=list)
    regressions: list[RegressionRule] = field(default_factory=list)
    description: str = ""
    coaching_cues: str = ""


# ── Session Catalog ──────────────────────────────────────────────────────

CATALOG: dict[str, WorkoutType] = {}


def _reg(w: WorkoutType) -> WorkoutType:
    CATALOG[w.name] = w
    return w


# --- Easy / Recovery ---

_reg(WorkoutType(
    name="Easy Run",
    category="Easy Run",
    intent="aerobic_development",
    energy_system="aerobic",
    daniels_pace="E",
    phase_affinity=["Base", "Build", "Peak", "Taper", "Recovery"],
    rpe_range=(3, 4),
    description="Steady easy-pace running for aerobic base and recovery promotion.",
    coaching_cues="Conversational pace. Relaxed shoulders, light footstrike.",
))

_reg(WorkoutType(
    name="Recovery Run",
    category="Recovery Run",
    intent="active_recovery",
    energy_system="aerobic",
    daniels_pace="E",
    phase_affinity=["Base", "Build", "Peak", "Taper", "Recovery"],
    rpe_range=(2, 3),
    description="Very easy effort to promote blood flow and recovery without training stress.",
    coaching_cues="Slower than easy pace. If in doubt, go slower.",
))

# --- Long Runs ---

_reg(WorkoutType(
    name="Long Run",
    category="Long Run",
    intent="aerobic_durability",
    energy_system="aerobic",
    daniels_pace="E",
    phase_affinity=["Base", "Build", "Peak"],
    rpe_range=(3, 5),
    description="Extended easy-pace run for aerobic endurance and fat oxidation.",
    coaching_cues="Even effort throughout. Fuel early for sessions over 75 min.",
))

_reg(WorkoutType(
    name="Long Run with M-Pace Finish",
    category="Long Run",
    intent="marathon_specific_endurance",
    energy_system="aerobic",
    daniels_pace="M",
    phase_affinity=["Build", "Peak"],
    rpe_range=(4, 6),
    intervals=[
        IntervalBlock(reps=1, work_duration_min=20, work_pace="M", recovery_duration_min=0, recovery_pace="E",
                      description="Final 20 min at marathon pace"),
    ],
    progressions=[
        ProgressionRule(trigger="Completed at target HR x2 sessions", action="+5 min M-pace finish", guard="ACR <= 1.1"),
    ],
    regressions=[
        RegressionRule(trigger="HR drift > 5% in M-pace segment", action="Reduce M-pace to 10 min", fallback_type="Long Run"),
    ],
    description="Long run finishing at marathon pace to build specific endurance.",
    coaching_cues="Run first 60-70% at E pace, then settle into M pace for the finish.",
))

# --- Marathon Pace ---

_reg(WorkoutType(
    name="Marathon Pace Run",
    category="Marathon Pace",
    intent="marathon_race_specific",
    energy_system="aerobic",
    daniels_pace="M",
    phase_affinity=["Build", "Peak"],
    rpe_range=(5, 6),
    intervals=[
        IntervalBlock(reps=1, work_duration_min=30, work_pace="M", recovery_duration_min=0, recovery_pace="E",
                      description="Sustained marathon-pace block"),
    ],
    progressions=[
        ProgressionRule(trigger="Readiness >= 3.5 for 2 weeks", action="+5 min sustained M block", guard="No pain flags"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0", action="Split into 2x15 min with 3 min E recovery", fallback_type="Easy Run"),
    ],
    description="Sustained running at marathon goal pace for pacing discipline.",
    coaching_cues="Lock into M pace from the start. Practice race-day fueling.",
))

# --- Tempo / Threshold ---

_reg(WorkoutType(
    name="Tempo Run",
    category="Tempo / Threshold",
    intent="lactate_threshold",
    energy_system="lactate_threshold",
    daniels_pace="T",
    phase_affinity=["Build", "Peak"],
    rpe_range=(6, 7),
    intervals=[
        IntervalBlock(reps=1, work_duration_min=20, work_pace="T", recovery_duration_min=0, recovery_pace="E",
                      description="Continuous threshold effort"),
    ],
    progressions=[
        ProgressionRule(trigger="Readiness >= 3.5 for 2 weeks", action="+5 min continuous block", guard="ACR <= 1.2"),
        ProgressionRule(trigger="Completed at target HR x3 sessions", action="+3 min tempo duration"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0", action="Split into cruise intervals", fallback_type="Cruise Intervals"),
        RegressionRule(trigger="Pain flag", action="Swap to easy run", fallback_type="Easy Run"),
    ],
    description="Continuous run at threshold pace — the bread and butter of lactate clearance work.",
    coaching_cues="Comfortably hard. You can speak in short phrases but not hold a conversation.",
))

_reg(WorkoutType(
    name="Cruise Intervals",
    category="Tempo / Threshold",
    intent="lactate_threshold",
    energy_system="lactate_threshold",
    daniels_pace="T",
    phase_affinity=["Build", "Peak"],
    rpe_range=(6, 7),
    intervals=[
        IntervalBlock(reps=4, work_duration_min=5, work_pace="T", recovery_duration_min=1, recovery_pace="E",
                      description="Threshold repeats with short recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Completed at target HR", action="+1 rep", guard="ACR <= 1.1"),
        ProgressionRule(trigger="Readiness >= 4.0", action="+2 min per rep duration"),
    ],
    regressions=[
        RegressionRule(trigger="HR drift > 5%", action="-1 rep"),
        RegressionRule(trigger="Pain flag", action="Swap to easy run", fallback_type="Easy Run"),
    ],
    description="Broken threshold work: same physiological benefit as tempo but more recoverable.",
    coaching_cues="Each rep at T pace. Recovery is a jog, not a stop. Stay smooth.",
))

_reg(WorkoutType(
    name="Threshold Repeats",
    category="Tempo / Threshold",
    intent="lactate_threshold",
    energy_system="lactate_threshold",
    daniels_pace="T",
    phase_affinity=["Base", "Build"],
    rpe_range=(6, 7),
    intervals=[
        IntervalBlock(reps=5, work_duration_min=3, work_pace="T", recovery_duration_min=2, recovery_pace="E",
                      description="Shorter threshold reps with moderate recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Completed at target x2", action="+1 rep or +1 min per rep"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0 or ACR > 1.3", action="-1 rep, +30s recovery"),
    ],
    description="Shorter threshold efforts with slightly longer recovery — good intro to T-pace work.",
    coaching_cues="Same pace as cruise intervals but shorter reps. Focus on consistent pace.",
))

# --- VO2max / Interval ---

_reg(WorkoutType(
    name="VO2max Intervals",
    category="VO2 Intervals",
    intent="vo2max_development",
    energy_system="vo2max",
    daniels_pace="I",
    phase_affinity=["Build", "Peak"],
    rpe_range=(8, 9),
    intervals=[
        IntervalBlock(reps=5, work_duration_min=4, work_pace="I", recovery_duration_min=3, recovery_pace="E",
                      description="Hard intervals at I pace with equal-ish recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="ACR <= 1.0 + green readiness", action="+1 rep", guard="Max 7 reps"),
        ProgressionRule(trigger="Readiness >= 4.2 x2 sessions", action="+30s work duration per rep"),
    ],
    regressions=[
        RegressionRule(trigger="ACR > 1.3", action="-1 rep, +30s recovery"),
        RegressionRule(trigger="Pain flag", action="Swap to easy run", fallback_type="Easy Run"),
    ],
    description="Classic VO2max intervals at I pace — the most effective session for aerobic power.",
    coaching_cues="Hard but controlled. Each rep should feel identical. Recovery is a jog, not a walk.",
))

_reg(WorkoutType(
    name="VO2max Short Intervals",
    category="VO2 Intervals",
    intent="vo2max_development",
    energy_system="vo2max",
    daniels_pace="I",
    phase_affinity=["Build", "Peak"],
    rpe_range=(8, 9),
    intervals=[
        IntervalBlock(reps=8, work_duration_min=2, work_pace="I", recovery_duration_min=2, recovery_pace="E",
                      description="Shorter VO2max intervals for higher rep count"),
    ],
    progressions=[
        ProgressionRule(trigger="Green readiness + completed all reps", action="+2 reps", guard="Max 12 reps"),
    ],
    regressions=[
        RegressionRule(trigger="RPE > target by 2+", action="-2 reps, extend recovery to 2.5 min"),
    ],
    description="Higher-rep VO2max work with shorter intervals — accumulate time at VO2max.",
    coaching_cues="Slightly faster than long intervals but same controlled effort. Consistency is key.",
))

# --- Repetition / Speed ---

_reg(WorkoutType(
    name="Repetitions",
    category="Repetitions",
    intent="speed_economy",
    energy_system="anaerobic",
    daniels_pace="R",
    phase_affinity=["Build", "Peak"],
    rpe_range=(8, 9),
    intervals=[
        IntervalBlock(reps=10, work_duration_min=0.67, work_pace="R", recovery_duration_min=2, recovery_pace="E",
                      description="200-400m reps at R pace with full recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Completed all reps at target pace", action="+2 reps", guard="Max 14 reps"),
    ],
    regressions=[
        RegressionRule(trigger="RPE exceeds target by >= 2", action="-2 reps, extend recovery"),
        RegressionRule(trigger="Pain flag", action="Swap to strides", fallback_type="Strides"),
    ],
    description="Short, fast reps to develop speed and running economy. Full recovery between reps.",
    coaching_cues="Fast and relaxed. Think quick turnover, not straining. Full recovery is essential.",
))

# --- Hill Work ---

_reg(WorkoutType(
    name="Hill Repeats",
    category="Hill Repeats",
    intent="neuromuscular_strength",
    energy_system="neuromuscular",
    daniels_pace="I",
    phase_affinity=["Base", "Build"],
    rpe_range=(7, 8),
    intervals=[
        IntervalBlock(reps=8, work_duration_min=1.5, work_pace="I", recovery_duration_min=2, recovery_pace="E",
                      description="60-90s uphill at I-effort with jog-down recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Readiness >= 3.5 x2 sessions", action="+2 reps", guard="Max 12 reps"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0", action="-2 reps"),
        RegressionRule(trigger="Pain flag", action="Swap to easy run", fallback_type="Easy Run"),
    ],
    description="Hill repeats for strength, power, and running economy.",
    coaching_cues="Drive knees, pump arms, maintain posture. Jog down easy for recovery.",
))

# --- Fartlek ---

_reg(WorkoutType(
    name="Fartlek",
    category="Fartlek",
    intent="mixed_pace_fitness",
    energy_system="aerobic_anaerobic",
    daniels_pace="T",
    phase_affinity=["Base", "Build"],
    rpe_range=(5, 7),
    intervals=[
        IntervalBlock(reps=6, work_duration_min=3, work_pace="T", recovery_duration_min=2, recovery_pace="E",
                      description="Surge/float: T-pace surges with E-pace floats"),
    ],
    progressions=[
        ProgressionRule(trigger="Readiness >= 3.5", action="+1 surge or +1 min per surge"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0", action="Reduce surges to E-M effort", fallback_type="Easy Run"),
    ],
    description="Unstructured pace variation — surges at T pace interspersed with easy running.",
    coaching_cues="Play with pace. Surges are controlled, not all-out. Stay relaxed on the floats.",
))

# --- Strides ---

_reg(WorkoutType(
    name="Strides",
    category="Strides / Neuromuscular",
    intent="neuromuscular_activation",
    energy_system="neuromuscular",
    daniels_pace="R",
    phase_affinity=["Base", "Build", "Peak", "Taper"],
    rpe_range=(5, 7),
    intervals=[
        IntervalBlock(reps=8, work_duration_min=0.33, work_pace="R", recovery_duration_min=1, recovery_pace="E",
                      description="20s accelerations with walk-back recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Completed smoothly", action="+2 strides", guard="Max 12 strides"),
    ],
    regressions=[
        RegressionRule(trigger="Pain flag or readiness < 3.0", action="-2 strides or skip"),
    ],
    description="Short accelerations at R pace embedded within an easy run.",
    coaching_cues="Smooth acceleration to near-sprint. Focus on form, not speed.",
))

# --- Race-Specific ---

_reg(WorkoutType(
    name="Race Pace Run",
    category="Race Pace",
    intent="race_specific",
    energy_system="race_specific",
    daniels_pace="M",
    phase_affinity=["Peak", "Taper"],
    rpe_range=(6, 8),
    intervals=[
        IntervalBlock(reps=3, work_duration_min=8, work_pace="M", recovery_duration_min=2, recovery_pace="E",
                      description="Race-pace blocks with brief recovery"),
    ],
    progressions=[
        ProgressionRule(trigger="Readiness >= 3.5", action="+1 rep or +2 min per rep"),
    ],
    regressions=[
        RegressionRule(trigger="Readiness < 3.0", action="-1 rep, extend recovery to 3 min"),
    ],
    description="Race-pace blocks to dial in goal pace feel and pacing discipline.",
    coaching_cues="Lock into race pace from the first step. Practice your race-day routine.",
))

_reg(WorkoutType(
    name="Race Rehearsal",
    category="Race Pace",
    intent="race_dress_rehearsal",
    energy_system="race_specific",
    daniels_pace="M",
    phase_affinity=["Peak"],
    rpe_range=(6, 7),
    intervals=[
        IntervalBlock(reps=1, work_duration_min=40, work_pace="M", recovery_duration_min=0, recovery_pace="E",
                      description="Extended race-pace dress rehearsal"),
    ],
    progressions=[],
    regressions=[
        RegressionRule(trigger="Readiness < 3.5", action="Reduce to 20 min at M pace"),
    ],
    description="Full dress rehearsal at goal pace — race kit, fueling, pacing strategy.",
    coaching_cues="Simulate race day exactly. Gear, nutrition, warmup, pacing.",
))

# --- Benchmark ---

_reg(WorkoutType(
    name="Benchmark / Time Trial",
    category="Benchmark / Time Trial",
    intent="fitness_assessment",
    energy_system="vo2max",
    daniels_pace="I",
    phase_affinity=["Base", "Build"],
    rpe_range=(8, 9),
    description="Controlled time trial to assess current fitness and update VDOT.",
    coaching_cues="Even-pace effort. Use this to recalibrate training paces.",
))

# --- Taper ---

_reg(WorkoutType(
    name="Taper / Openers",
    category="Taper / Openers",
    intent="race_priming",
    energy_system="neuromuscular",
    daniels_pace="T",
    phase_affinity=["Taper"],
    rpe_range=(4, 6),
    intervals=[
        IntervalBlock(reps=4, work_duration_min=1, work_pace="T", recovery_duration_min=2, recovery_pace="E",
                      description="Short T-pace openers to prime the system"),
    ],
    description="Low-volume sharpening session to prime neuromuscular system before race.",
    coaching_cues="Short and snappy. You should feel fast and fresh, not tired.",
))

# --- Cross-Training ---

_reg(WorkoutType(
    name="Cross-Training",
    category="Cross-Training Optional",
    intent="aerobic_support",
    energy_system="aerobic",
    daniels_pace="E",
    phase_affinity=["Base", "Recovery", "Taper"],
    rpe_range=(2, 4),
    description="Low-impact aerobic cross-training (cycling, swimming, elliptical).",
    coaching_cues="Keep heart rate in E zone. This is for recovery, not fitness gain.",
))


# ── Phase Templates (Daniels-informed, distance-specific) ────────────────

# Generic fallback templates (used when race_goal is not recognised)
PHASE_TEMPLATES: dict[str, list[str]] = {
    "Base": [
        "Easy Run", "Long Run", "Strides", "Recovery Run",
        "Hill Repeats", "Easy Run", "Cross-Training",
    ],
    "Build": [
        "Tempo Run", "VO2max Intervals", "Long Run with M-Pace Finish",
        "Easy Run", "Cruise Intervals", "Recovery Run", "Hill Repeats",
    ],
    "Peak": [
        "Race Pace Run", "VO2max Intervals", "Long Run with M-Pace Finish",
        "Recovery Run", "Cruise Intervals", "Repetitions", "Easy Run",
    ],
    "Taper": [
        "Taper / Openers", "Easy Run", "Race Pace Run",
        "Recovery Run", "Strides", "Easy Run", "Cross-Training",
    ],
    "Recovery": [
        "Recovery Run", "Easy Run", "Cross-Training",
        "Easy Run", "Recovery Run", "Cross-Training", "Recovery Run",
    ],
}

# Distance-specific templates keyed by race goal.
# Session order is priority-ranked: first sessions are most important when
# sessions_per_week is lower than the full template length.

DISTANCE_PHASE_TEMPLATES: dict[str, dict[str, list[str]]] = {
    # --- Middle distance (800m / 1500m / Mile) ---
    # Emphasis: VO2max and R-pace economy; shorter long runs; minimal marathon work
    "800m": {
        "Base": [
            "Easy Run", "Strides", "Hill Repeats", "Long Run",
            "Recovery Run", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "VO2max Short Intervals", "Repetitions", "Tempo Run",
            "Easy Run", "Hill Repeats", "Strides", "Recovery Run",
        ],
        "Peak": [
            "Repetitions", "VO2max Short Intervals", "Race Pace Run",
            "Easy Run", "Strides", "Recovery Run", "Cross-Training",
        ],
        "Taper": [
            "Taper / Openers", "Strides", "Easy Run",
            "Recovery Run", "Cross-Training", "Easy Run", "Recovery Run",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    "1500m": {
        "Base": [
            "Easy Run", "Strides", "Hill Repeats", "Long Run",
            "Recovery Run", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "VO2max Intervals", "Repetitions", "Tempo Run",
            "Easy Run", "Hill Repeats", "Strides", "Recovery Run",
        ],
        "Peak": [
            "VO2max Intervals", "Repetitions", "Race Pace Run",
            "Easy Run", "Strides", "Recovery Run", "Cross-Training",
        ],
        "Taper": [
            "Taper / Openers", "Strides", "Easy Run",
            "Recovery Run", "Cross-Training", "Easy Run", "Recovery Run",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    "Mile": {
        "Base": [
            "Easy Run", "Strides", "Hill Repeats", "Long Run",
            "Recovery Run", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "VO2max Intervals", "Repetitions", "Tempo Run",
            "Easy Run", "Hill Repeats", "Strides", "Recovery Run",
        ],
        "Peak": [
            "VO2max Intervals", "Repetitions", "Race Pace Run",
            "Easy Run", "Strides", "Recovery Run", "Cross-Training",
        ],
        "Taper": [
            "Taper / Openers", "Strides", "Easy Run",
            "Recovery Run", "Cross-Training", "Easy Run", "Recovery Run",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    # --- 5K ---
    # Emphasis: VO2max primary, threshold secondary; moderate long run
    "5K": {
        "Base": [
            "Easy Run", "Long Run", "Strides", "Recovery Run",
            "Hill Repeats", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "VO2max Intervals", "Tempo Run", "Cruise Intervals",
            "Easy Run", "Long Run", "Strides", "Recovery Run",
        ],
        "Peak": [
            "VO2max Intervals", "Repetitions", "Tempo Run",
            "Race Pace Run", "Easy Run", "Recovery Run", "Strides",
        ],
        "Taper": [
            "Taper / Openers", "Strides", "Easy Run",
            "Race Pace Run", "Recovery Run", "Easy Run", "Cross-Training",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    # --- 10K ---
    # Emphasis: balanced VO2max and threshold; longer long run
    "10K": {
        "Base": [
            "Easy Run", "Long Run", "Strides", "Recovery Run",
            "Hill Repeats", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "Tempo Run", "VO2max Intervals", "Cruise Intervals",
            "Long Run", "Easy Run", "Recovery Run", "Hill Repeats",
        ],
        "Peak": [
            "VO2max Intervals", "Race Pace Run", "Tempo Run",
            "Cruise Intervals", "Easy Run", "Recovery Run", "Strides",
        ],
        "Taper": [
            "Taper / Openers", "Easy Run", "Race Pace Run",
            "Recovery Run", "Strides", "Easy Run", "Cross-Training",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    # --- Half Marathon ---
    # Emphasis: threshold primary, M-pace long runs; VO2max for speed reserve
    "Half Marathon": {
        "Base": [
            "Easy Run", "Long Run", "Strides", "Recovery Run",
            "Hill Repeats", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "Tempo Run", "Long Run with M-Pace Finish", "VO2max Intervals",
            "Cruise Intervals", "Easy Run", "Recovery Run", "Hill Repeats",
        ],
        "Peak": [
            "Race Pace Run", "Long Run with M-Pace Finish", "VO2max Intervals",
            "Tempo Run", "Easy Run", "Recovery Run", "Strides",
        ],
        "Taper": [
            "Taper / Openers", "Easy Run", "Race Pace Run",
            "Recovery Run", "Strides", "Easy Run", "Cross-Training",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
    # --- Marathon ---
    # Emphasis: M-pace endurance primary; long runs with M-pace finish;
    # threshold for fatigue resistance; VO2max for aerobic ceiling
    "Marathon": {
        "Base": [
            "Easy Run", "Long Run", "Strides", "Recovery Run",
            "Hill Repeats", "Fartlek", "Cross-Training",
        ],
        "Build": [
            "Long Run with M-Pace Finish", "Marathon Pace Run", "Tempo Run",
            "VO2max Intervals", "Easy Run", "Recovery Run", "Cruise Intervals",
        ],
        "Peak": [
            "Marathon Pace Run", "Long Run with M-Pace Finish", "Race Rehearsal",
            "VO2max Intervals", "Easy Run", "Recovery Run", "Tempo Run",
        ],
        "Taper": [
            "Taper / Openers", "Easy Run", "Race Pace Run",
            "Marathon Pace Run", "Recovery Run", "Easy Run", "Cross-Training",
        ],
        "Recovery": PHASE_TEMPLATES["Recovery"],
    },
}

# Distance-specific phase allocation: (base_end, build_end, peak_end) as fractions of total_weeks.
# Remaining fraction after peak_end is Taper.
DISTANCE_PHASE_SPLITS: dict[str, tuple[float, float, float]] = {
    "800m":          (0.25, 0.60, 0.85),
    "1500m":         (0.25, 0.60, 0.85),
    "Mile":          (0.25, 0.60, 0.85),
    "5K":            (0.30, 0.65, 0.88),
    "10K":           (0.35, 0.65, 0.88),
    "Half Marathon":  (0.35, 0.65, 0.85),
    "Marathon":       (0.40, 0.70, 0.88),
}


def get_phase_sessions(
    phase: str,
    sessions_per_week: int,
    race_goal: str | None = None,
) -> list[str]:
    """Return the Daniels-informed session sequence for a phase, capped at sessions_per_week.

    When race_goal is provided, selects from distance-specific templates that
    prioritise the workouts most relevant for that race distance.
    Falls back to generic templates for unrecognised distances.
    """
    if race_goal and race_goal in DISTANCE_PHASE_TEMPLATES:
        dist_templates = DISTANCE_PHASE_TEMPLATES[race_goal]
        template = dist_templates.get(phase, PHASE_TEMPLATES.get(phase, PHASE_TEMPLATES["Base"]))
    else:
        template = PHASE_TEMPLATES.get(phase, PHASE_TEMPLATES["Base"])
    return template[:sessions_per_week]


def get_workout_type(name: str) -> WorkoutType | None:
    """Look up a workout type by name from the catalog."""
    return CATALOG.get(name)


def build_prescriptive_structure(
    workout: WorkoutType,
    duration_min: int,
    environment: str = "outdoor",
) -> dict[str, Any]:
    """Build a complete structure_json with prescriptive interval blocks for a workout type.

    Allocates warmup (~20%), cooldown (6-8 min), and distributes remaining
    time to the main_set with interval detail when available.
    """
    total = max(20, duration_min)
    warmup_min = max(8, total // 5)
    cooldown_min = 8 if total >= 45 else 6
    main_min = max(8, total - warmup_min - cooldown_min)

    blocks: list[dict[str, Any]] = [
        {
            "phase": "warmup",
            "duration_min": warmup_min,
            "instructions": "Easy jog with mobility drills. Build to workout pace over last 2 min.",
            "target": {"pace_label": "E", "rpe_range": [2, 3]},
        },
    ]

    main_block: dict[str, Any] = {
        "phase": "main_set",
        "duration_min": main_min,
        "target": {"pace_label": workout.daniels_pace, "rpe_range": list(workout.rpe_range)},
    }

    if workout.intervals:
        interval_defs = []
        for ivl in workout.intervals:
            interval_defs.append({
                "reps": ivl.reps,
                "work_duration_min": ivl.work_duration_min,
                "work_pace": ivl.work_pace,
                "recovery_duration_min": ivl.recovery_duration_min,
                "recovery_pace": ivl.recovery_pace,
                "description": ivl.description,
            })
        main_block["intervals"] = interval_defs
        main_block["instructions"] = workout.intervals[0].description
    else:
        main_block["instructions"] = workout.description
        main_block["intervals"] = []

    blocks.append(main_block)

    blocks.append({
        "phase": "cooldown",
        "duration_min": cooldown_min,
        "instructions": "Easy jog, then light stretching and controlled breathing.",
        "target": {"pace_label": "E", "rpe_range": [2, 3]},
    })

    return {
        "version": 3,
        "environment": environment,
        "workout_type": workout.name,
        "daniels_pace": workout.daniels_pace,
        "blocks": blocks,
        "fueling_hint": "Hydrate pre-session; add carbs for sessions >60 min." if total > 60 else "Hydrate pre-session.",
        "success_criteria": workout.coaching_cues or "Hit target paces with controlled effort.",
    }


def build_prescriptive_targets(workout: WorkoutType) -> dict[str, Any]:
    """Build targets_json using Daniels pace labels instead of generic zones."""
    return {
        "primary": {
            "pace_label": workout.daniels_pace,
            "rpe_range": list(workout.rpe_range),
        },
        "secondary": {
            "cadence_spm": [170, 185],
            "terrain": "flat_or_rolling",
        },
    }


def build_prescriptive_progression(workout: WorkoutType) -> dict[str, Any]:
    """Build progression_json from the workout's progression rules."""
    result: dict[str, Any] = {}
    for i, rule in enumerate(workout.progressions):
        result[f"rule_{i+1}"] = {
            "trigger": rule.trigger,
            "action": rule.action,
            "guard": rule.guard,
        }
    if not result:
        result["rule_1"] = {"trigger": "Readiness >= 3.5 x2 sessions", "action": "+5 min duration", "guard": ""}
    return result


def build_prescriptive_regression(workout: WorkoutType) -> dict[str, Any]:
    """Build regression_json from the workout's regression rules."""
    result: dict[str, Any] = {}
    for i, rule in enumerate(workout.regressions):
        result[f"rule_{i+1}"] = {
            "trigger": rule.trigger,
            "action": rule.action,
            "fallback_type": rule.fallback_type,
        }
    if not result:
        result["rule_1"] = {"trigger": "Readiness < 3.0 or pain flag", "action": "Reduce volume 20%", "fallback_type": "Easy Run"}
    return result
