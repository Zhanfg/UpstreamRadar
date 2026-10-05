<?php
declare(strict_types=1);

function classifyComposerConstraint(string $raw): string {
    $value = strtolower(trim($raw));
    if ($value === '' || $value === '*' || $value === 'dev-master' || $value === 'dev-main') return 'floating';
    if (str_starts_with($value, 'dev-')) return 'development-branch';
    if (str_contains($value, '@dev')) return 'development-stability';
    if (str_starts_with($value, '^') || str_starts_with($value, '~')) return 'compatible-range';
    if (str_contains($value, '>') || str_contains($value, '<') || str_contains($value, '||')) return 'explicit-range';
    return 'exact-or-tag';
}

function clamp01(float $value): float {
    return max(0.0, min(1.0, $value));
}

function bernoulliKL(float $q, float $p): float {
    $eps = 1.0e-12;
    $q = max($eps, min(1.0 - $eps, $q));
    $p = max($eps, min(1.0 - $eps, $p));
    return $q * log($q / $p) + (1.0 - $q) * log((1.0 - $q) / (1.0 - $p));
}

function bayesianSurprise(float $empirical, float $predicted): float {
    return clamp01(1.0 - exp(-3.4 * bernoulliKL($empirical, $predicted)));
}

function composerRisk(string $raw): float {
    $kind = classifyComposerConstraint($raw);
    $risk = match ($kind) {
        'floating' => 0.82,
        'development-branch' => 0.72,
        'development-stability' => 0.65,
        'explicit-range' => 0.36,
        'compatible-range' => 0.20,
        default => 0.06,
    };
    if (str_contains(strtolower($raw), 'git')) $risk += 0.10;
    return clamp01($risk);
}

if (PHP_SAPI === 'cli' && isset($argv)) {
    foreach (array_slice($argv, 1) as $value) {
        echo $value, "\t", classifyComposerConstraint($value), PHP_EOL;
    }
}
