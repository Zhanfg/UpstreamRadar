import strutils

type
  ReleaseTag* = object
    major*: int
    minor*: int
    patch*: int
    prerelease*: string

proc parseReleaseTag*(raw: string): ReleaseTag =
  var value = raw.strip()
  if value.len > 0 and (value[0] == 'v' or value[0] == 'V'):
    value = value[1 .. ^1]

  let dash = value.find('-')
  var core = value
  if dash >= 0:
    core = value[0 ..< dash]
    result.prerelease = value[dash + 1 .. ^1]

  let parts = core.split('.')
  if parts.len < 2 or parts.len > 3:
    raise newException(ValueError, "expected major.minor[.patch]")

  result.major = parseInt(parts[0])
  result.minor = parseInt(parts[1])
  result.patch = if parts.len == 3: parseInt(parts[2]) else: 0

proc isStable*(tag: ReleaseTag): bool =
  tag.prerelease.len == 0


proc clamp01(value: float): float =
  max(0.0, min(1.0, value))

proc releaseRisk*(tag: ReleaseTag): float =
  if tag.prerelease.len == 0:
    return 0.0
  let value = tag.prerelease.toLowerAscii()
  var risk = 0.35
  if "alpha" in value or "dev" in value or "nightly" in value:
    risk += 0.35
  if "beta" in value:
    risk += 0.20
  if "rc" in value:
    risk += 0.10
  clamp01(risk)

proc compatibilityConfidence*(current, previous: ReleaseTag): float =
  let majorJump = if current.major != previous.major: 1.0 else: 0.0
  let minorJump = if current.major == previous.major and current.minor != previous.minor: 1.0 else: 0.0
  clamp01(1.0 - (0.65 * majorJump + 0.25 * minorJump + 0.10 * releaseRisk(current)))
