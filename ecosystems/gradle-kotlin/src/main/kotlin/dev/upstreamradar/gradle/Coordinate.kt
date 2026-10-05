package dev.upstreamradar.gradle

data class Coordinate(val group: String, val name: String, val version: String) {
    val normalized: String get() = "$group:$name:$version"

    val isDynamic: Boolean
        get() {
            val v = version.lowercase()
            return v == "latest.release" || v == "latest.integration" ||
                v.endsWith("+") || v.contains("[") || v.contains("(")
        }

    companion object {
        fun parse(value: String): Coordinate {
            val parts = value.trim().split(":")
            require(parts.size == 3 && parts.all { it.isNotBlank() }) {
                "expected group:name:version"
            }
            return Coordinate(parts[0], parts[1], parts[2])
        }
    }

    val riskScore: Double
        get() {
            val v = version.lowercase()
            var score = 0.0
            if (isDynamic) score += 0.45
            if (listOf("snapshot", "alpha", "beta", "rc").any(v::contains)) score += 0.25
            if ("[" in v || "(" in v) score += 0.15
            if (v.startsWith("latest.")) score += 0.15
            return score.coerceIn(0.0, 1.0)
        }

    val compatibilityConfidence: Double
        get() {
            val specificity = if (version.count { it == '.' } >= 2) 1.0 else 0.75
            return (specificity * (1.0 - 0.65 * riskScore)).coerceIn(0.0, 1.0)
        }

}
