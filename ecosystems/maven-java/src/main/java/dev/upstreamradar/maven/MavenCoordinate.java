package dev.upstreamradar.maven;

public record MavenCoordinate(String group, String artifact, String version) {
    public static MavenCoordinate parse(String value) {
        String[] parts = value.trim().split(":", -1);
        if (parts.length != 3 || parts[0].isBlank() || parts[1].isBlank() || parts[2].isBlank()) {
            throw new IllegalArgumentException("expected group:artifact:version");
        }
        return new MavenCoordinate(parts[0], parts[1], parts[2]);
    }

    public boolean isDynamic() {
        String v = version.toLowerCase();
        return v.contains("snapshot") || v.equals("latest") || v.equals("release")
            || v.contains("[") || v.contains("(") || v.endsWith("+");
    }

    public String normalized() {
        return group + ":" + artifact + ":" + version;
    }

    public double riskScore() {
        String v = version.toLowerCase();
        double score = 0.0;
        if (isDynamic()) score += 0.45;
        if (v.contains("snapshot") || v.contains("alpha") || v.contains("beta") || v.contains("rc")) score += 0.25;
        if (v.contains("[") || v.contains("(")) score += 0.15;
        if (v.equals("latest") || v.equals("release")) score += 0.15;
        return Math.min(1.0, score);
    }

    public double compatibilityConfidence() {
        double risk = riskScore();
        double specificity = version.chars().filter(ch -> ch == '.').count() >= 2 ? 1.0 : 0.75;
        return Math.max(0.0, Math.min(1.0, specificity * (1.0 - 0.65 * risk)));
    }

}
