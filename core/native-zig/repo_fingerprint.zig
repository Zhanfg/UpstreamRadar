const std = @import("std");

fn fnv1a64(bytes: []const u8) u64 {
    var hash: u64 = 0xcbf29ce484222325;
    for (bytes) |byte| {
        hash ^= @as(u64, byte);
        hash *%= 0x100000001b3;
    }
    return hash;
}

fn clamp01(value: f64) f64 {
    return @max(0.0, @min(1.0, value));
}

pub fn bernoulliKl(q0: f64, p0: f64) f64 {
    const eps = 1e-12;
    const q = @max(eps, @min(1.0 - eps, q0));
    const p = @max(eps, @min(1.0 - eps, p0));
    return q * @log(q / p) + (1.0 - q) * @log((1.0 - q) / (1.0 - p));
}

pub fn bayesianSurprise(empirical: f64, predicted: f64) f64 {
    return clamp01(1.0 - @exp(-3.4 * bernoulliKl(empirical, predicted)));
}

pub fn riskAdjusted(utility: f64, tail_risk: f64, reliability: f64) f64 {
    return @max(0.0, utility)
        * (1.0 - 0.11 * clamp01(tail_risk))
        * (0.82 + 0.18 * clamp01(reliability));
}

pub fn main() !void {
    var args = std.process.args();
    _ = args.next();
    const out = std.io.getStdOut().writer();
    while (args.next()) |name| {
        try out.print("{x:0>16}\t{s}\n", .{ fnv1a64(name), name });
    }
}
