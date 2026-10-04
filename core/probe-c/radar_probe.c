#define _DEFAULT_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

static long long monotonic_ms(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return -1;
    return (long long)ts.tv_sec * 1000LL + ts.tv_nsec / 1000000LL;
}

int main(void) {
    long cpus = sysconf(_SC_NPROCESSORS_ONLN);
    double load[3] = {0.0, 0.0, 0.0};
    int loads = getloadavg(load, 3);
    if (cpus < 1) cpus = 1;
    printf("{\"monotonic_ms\":%lld,\"online_cpus\":%ld", monotonic_ms(), cpus);
    if (loads > 0) {
        double pressure = load[0] / (double)cpus;
        if (pressure < 0.0) pressure = 0.0;
        if (pressure > 4.0) pressure = 4.0;
        pressure = 1.0 - exp(-pressure);
        printf(",\"load1\":%.3f,\"pressure\":%.6f", load[0], pressure);
    }
    if (loads > 1) printf(",\"load5\":%.3f", load[1]);
    if (loads > 2) printf(",\"load15\":%.3f", load[2]);
    puts("}");
    return 0;
}
