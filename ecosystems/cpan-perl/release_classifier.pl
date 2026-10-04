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

sub clamp01 {
    my ($value) = @_;
    return 0 if $value < 0;
    return 1 if $value > 1;
    return $value;
}

sub release_risk {
    my ($version) = @_;
    my $kind = classify_release($version);
    my %base = (
        unknown   => 0.50,
        developer => 0.78,
        trial     => 0.62,
        stable    => 0.08,
        custom    => 0.38,
    );
    return clamp01($base{$kind} // 0.50);
}

sub bayesian_surprise {
    my ($q, $p) = @_;
    my $eps = 1e-12;
    $q = $q < $eps ? $eps : $q > 1 - $eps ? 1 - $eps : $q;
    $p = $p < $eps ? $eps : $p > 1 - $eps ? 1 - $eps : $p;
    my $kl = $q * log($q / $p) + (1 - $q) * log((1 - $q) / (1 - $p));
    return clamp01(1 - exp(-3.4 * $kl));
}

unless (caller) {
    for my $version (@ARGV) {
        print "$version\t", classify_release($version), "\n";
    }
}
