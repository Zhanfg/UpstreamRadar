module Impact (Signals(..), impactScore, bayesianSurprise, tailRisk, riskAdjusted) where

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


bernoulliKL :: Double -> Double -> Double
bernoulliKL q0 p0 =
  let eps = 1e-12
      q = max eps (min (1 - eps) q0)
      p = max eps (min (1 - eps) p0)
  in q * log (q / p) + (1 - q) * log ((1 - q) / (1 - p))

bayesianSurprise :: Double -> Double -> Double
bayesianSurprise empirical predicted =
  clamp (1 - exp (-3.4 * bernoulliKL empirical predicted))

tailRisk :: [Double] -> Double
tailRisk [] = 0
tailRisk values =
  let xs = quicksort (map clamp values)
      start = min (length xs - 1) (floor (fromIntegral (length xs) * 0.75))
      tailValues = drop start xs
  in sum tailValues / fromIntegral (length tailValues)
  where
    quicksort [] = []
    quicksort (x:rest) =
      quicksort [a | a <- rest, a <= x] ++ [x] ++ quicksort [a | a <- rest, a > x]

riskAdjusted :: Double -> Double -> Double -> Double
riskAdjusted utility risk reliability =
  max 0 utility * (1 - 0.11 * clamp risk) * (0.82 + 0.18 * clamp reliability)
