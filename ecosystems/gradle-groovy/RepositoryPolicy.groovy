package upstreamradar.gradle

final class RepositoryPolicy {
    static Map<String, Object> analyze(String script) {
        String text = script ?: ""
        boolean hasMavenCentral = text.contains("mavenCentral()")
        boolean hasGoogle = text.contains("google()")
        boolean hasJcenter = text.contains("jcenter()")
        boolean hasInsecureProtocol =
            text.contains("allowInsecureProtocol = true") ||
            text.contains("allowInsecureProtocol=true")
        boolean hasFlatDir = text.contains("flatDir")

        int risk = 0
        if (hasJcenter) risk += 2
        if (hasInsecureProtocol) risk += 4
        if (hasFlatDir) risk += 1
        if (!hasMavenCentral && !hasGoogle) risk += 1

        return [
            mavenCentral: hasMavenCentral,
            google: hasGoogle,
            deprecatedJCenter: hasJcenter,
            insecureProtocol: hasInsecureProtocol,
            flatDir: hasFlatDir,
            riskScore: risk
        ]
    }
}
