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
}
