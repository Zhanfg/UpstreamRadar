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

if (PHP_SAPI === 'cli' && isset($argv)) {
    foreach (array_slice($argv, 1) as $value) {
        echo $value, "\t", classifyComposerConstraint($value), PHP_EOL;
    }
}
