using System;

namespace UpstreamRadar.NuGet;

public readonly record struct NuGetCoordinate(string Package, string Version)
{
    public static NuGetCoordinate Parse(string value)
    {
        var split = value.LastIndexOf('@');
        if (split <= 0 || split == value.Length - 1)
            throw new FormatException("expected Package@Version");
        return new NuGetCoordinate(value[..split].Trim(), value[(split + 1)..].Trim());
    }

    public bool IsFloating()
    {
        var version = Version.ToLowerInvariant();
        return version.Contains('*') || version.Contains("latest") || version.Contains("-*");
    }

    public override string ToString() => $"{Package}@{Version}";

    public double RiskScore()
    {
        var v = Version.ToLowerInvariant();
        var score = 0.0;
        if (IsFloating()) score += 0.45;
        if (v.Contains("alpha") || v.Contains("beta") || v.Contains("rc") || v.Contains("preview"))
            score += 0.25;
        if (v.Contains('[') || v.Contains('(')) score += 0.15;
        if (v.Contains("nightly") || v.Contains("dev")) score += 0.15;
        return Math.Clamp(score, 0.0, 1.0);
    }

    public double CompatibilityConfidence()
    {
        var dots = Version.Count(ch => ch == '.');
        var specificity = dots >= 2 ? 1.0 : 0.75;
        return Math.Clamp(specificity * (1.0 - 0.65 * RiskScore()), 0.0, 1.0);
    }

}
