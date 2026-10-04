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
}
