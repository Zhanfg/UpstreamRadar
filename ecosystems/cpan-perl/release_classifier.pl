use strict;
use warnings;

sub classify_release {
    my ($version) = @_;
    return 'unknown' unless defined $version && length $version;
    return 'developer' if $version =~ /_/;
    return 'trial' if $version =~ /(?:TRIAL|RC|alpha|beta)/i;
    return 'stable' if $version =~ /^v?\d+(?:\.\d+)+$/;
    return 'custom';
}

unless (caller) {
    for my $version (@ARGV) {
        print "$version\t", classify_release($version), "\n";
    }
}
