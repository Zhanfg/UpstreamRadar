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
}
