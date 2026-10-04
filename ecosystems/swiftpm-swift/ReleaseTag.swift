import Foundation

struct ReleaseTag: Comparable, CustomStringConvertible {
    let major: Int
    let minor: Int
    let patch: Int
    let prerelease: String?

    static func parse(_ raw: String) -> ReleaseTag? {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if value.hasPrefix("v") { value.removeFirst() }
        let pieces = value.split(separator: "-", maxSplits: 1).map(String.init)
        let core = pieces[0].split(separator: ".").map(String.init)
        guard core.count >= 2 && core.count <= 3,
              let major = Int(core[0]),
              let minor = Int(core[1]),
              let patch = Int(core.count == 3 ? core[2] : "0") else { return nil }
        return ReleaseTag(major: major, minor: minor, patch: patch,
                          prerelease: pieces.count == 2 ? pieces[1] : nil)
    }

    var isStable: Bool { prerelease == nil }

    var releaseRisk: Double {
        guard let prerelease else { return 0.0 }
        let value = prerelease.lowercased()
        var risk = 0.35
        if value.contains("alpha") || value.contains("dev") || value.contains("nightly") { risk += 0.35 }
        if value.contains("beta") { risk += 0.20 }
        if value.contains("rc") { risk += 0.10 }
        return min(1.0, risk)
    }

    func compatibilityConfidence(comparedTo previous: ReleaseTag) -> Double {
        let majorJump = major != previous.major ? 1.0 : 0.0
        let minorJump = major == previous.major && minor != previous.minor ? 1.0 : 0.0
        let distance = 0.65 * majorJump + 0.25 * minorJump + 0.10 * releaseRisk
        return max(0.0, min(1.0, 1.0 - distance))
    }

    var description: String {
        let core = "\(major).\(minor).\(patch)"
        return prerelease.map { core + "-" + $0 } ?? core
    }

    static func < (lhs: ReleaseTag, rhs: ReleaseTag) -> Bool {
        if lhs.major != rhs.major { return lhs.major < rhs.major }
        if lhs.minor != rhs.minor { return lhs.minor < rhs.minor }
        if lhs.patch != rhs.patch { return lhs.patch < rhs.patch }
        switch (lhs.prerelease, rhs.prerelease) {
        case (nil, nil): return false
        case (nil, _): return false
        case (_, nil): return true
        case let (a?, b?): return a < b
        }
    }
}
