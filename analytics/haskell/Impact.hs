module Impact (Signals(..), impactScore) where

data Signals = Signals
  { changeFraction :: Double
  , securitySignal :: Double
  , dependencyWeight :: Double
  , releaseSignal :: Double
  } deriving (Eq, Show)

clamp :: Double -> Double
clamp = max 0 . min 1

impactScore :: Signals -> Double
impactScore s =
  clamp $
    0.30 * clamp (changeFraction s) +
    0.30 * clamp (securitySignal s) +
    0.25 * clamp (dependencyWeight s) +
    0.15 * clamp (releaseSignal s)
