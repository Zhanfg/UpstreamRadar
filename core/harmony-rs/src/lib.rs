//! HARMONY Algorithm Museum reference runtime.
//!
//! The Rust implementation is intentionally self-contained and deterministic.
//! It is not a code-size mirror of the Python scheduler: the library exposes
//! typed primitives that can be embedded by collectors, benchmarks, or FFI
//! consumers while sharing the same conceptual evidence model.

pub mod bandit;
pub mod change;
pub mod graph;
pub mod information;
pub mod model;
pub mod optimization;
pub mod robust;
pub mod scheduler;
pub mod sketches;

pub use model::{
    Candidate, GalleryEvidence, MuseumEvidence, RepositorySignal, Schedule,
    SchedulerConfig,
};
pub use scheduler::HarmonyScheduler;

#[inline]
pub(crate) fn clamp01(value: f64) -> f64 {
    value.clamp(0.0, 1.0)
}

#[inline]
pub(crate) fn stable_sigmoid(value: f64) -> f64 {
    if value >= 0.0 {
        let z = (-value).exp();
        1.0 / (1.0 + z)
    } else {
        let z = value.exp();
        z / (1.0 + z)
    }
}
