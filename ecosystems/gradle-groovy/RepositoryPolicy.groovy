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

        def repositoryUrls = (text =~ /url\s*[=( ]+["']([^"']+)["']/).collect { it[1] as String }
        int httpRepositories = repositoryUrls.count { it.startsWith("http://") }
        int customRepositories = repositoryUrls.count {
            !(it.contains("maven.google.com") || it.contains("repo.maven.apache.org"))
        }
        def dynamicVersions = (text =~ /["'][^"']*[:@](?:latest[^"']*|[^"']*\+|[^"']*SNAPSHOT)["']/).size()

        double structuralRisk = Math.min(
            1.0d,
            0.10d * risk +
            0.18d * httpRepositories +
            0.08d * customRepositories +
            0.10d * dynamicVersions
        )

        return [
            mavenCentral: hasMavenCentral,
            google: hasGoogle,
            deprecatedJCenter: hasJcenter,
            insecureProtocol: hasInsecureProtocol,
            flatDir: hasFlatDir,
            repositoryUrls: repositoryUrls,
            dynamicVersions: dynamicVersions,
            riskScore: risk,
            structuralRisk: structuralRisk
        ]
    }
}
