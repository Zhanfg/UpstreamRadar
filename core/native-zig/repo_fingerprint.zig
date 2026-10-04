const std = @import("std");

fn fnv1a64(bytes: []const u8) u64 {
    var hash: u64 = 0xcbf29ce484222325;
    for (bytes) |byte| {
        hash ^= @as(u64, byte);
        hash *%= 0x100000001b3;
    }
    return hash;
}

pub fn main() !void {
    var args = std.process.args();
    _ = args.next();
    const out = std.io.getStdOut().writer();
    while (args.next()) |name| {
        try out.print("{x:0>16}\t{s}\n", .{ fnv1a64(name), name });
    }
}
