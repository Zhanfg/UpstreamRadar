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
