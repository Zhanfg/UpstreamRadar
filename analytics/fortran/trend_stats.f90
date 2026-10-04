module trend_stats
  implicit none
contains

  pure real(8) function mean_value(values) result(avg)
    real(8), intent(in) :: values(:)
    if (size(values) == 0) then
      avg = 0.0d0
    else
      avg = sum(values) / dble(size(values))
    end if
  end function mean_value

  pure real(8) function linear_slope(values) result(slope)
    real(8), intent(in) :: values(:)
    integer :: i, n
    real(8) :: mean_x, mean_y, numerator, denominator, dx

    n = size(values)
    if (n < 2) then
      slope = 0.0d0
      return
    end if

    mean_x = dble(n - 1) / 2.0d0
    mean_y = mean_value(values)
    numerator = 0.0d0
    denominator = 0.0d0

    do i = 1, n
      dx = dble(i - 1) - mean_x
      numerator = numerator + dx * (values(i) - mean_y)
      denominator = denominator + dx * dx
    end do

    if (denominator == 0.0d0) then
      slope = 0.0d0
    else
      slope = numerator / denominator
    end if
  end function linear_slope

  pure real(8) function clamp01(value) result(out)
    real(8), intent(in) :: value
    out = max(0.0d0, min(1.0d0, value))
  end function clamp01

  pure real(8) function bernoulli_kl(q0, p0) result(divergence)
    real(8), intent(in) :: q0, p0
    real(8), parameter :: eps = 1.0d-12
    real(8) :: q, p
    q = max(eps, min(1.0d0 - eps, q0))
    p = max(eps, min(1.0d0 - eps, p0))
    divergence = q * log(q / p) + (1.0d0 - q) * log((1.0d0 - q) / (1.0d0 - p))
  end function bernoulli_kl

  pure real(8) function bayesian_surprise(empirical, predicted) result(value)
    real(8), intent(in) :: empirical, predicted
    value = clamp01(1.0d0 - exp(-3.4d0 * bernoulli_kl(empirical, predicted)))
  end function bayesian_surprise

  real(8) function cvar(values, quantile) result(value)
    real(8), intent(in) :: values(:)
    real(8), intent(in) :: quantile
    real(8), allocatable :: sorted(:)
    real(8) :: q, tmp
    integer :: i, j, start_idx, n
    n = size(values)
    if (n == 0) then
      value = 0.0d0
      return
    end if
    allocate(sorted(n))
    sorted = max(0.0d0, min(1.0d0, values))
    do i = 1, n - 1
      do j = i + 1, n
        if (sorted(j) < sorted(i)) then
          tmp = sorted(i)
          sorted(i) = sorted(j)
          sorted(j) = tmp
        end if
      end do
    end do
    q = max(0.5d0, min(0.999999d0, quantile))
    start_idx = int(floor(dble(n - 1) * q)) + 1
    value = sum(sorted(start_idx:n)) / dble(n - start_idx + 1)
    deallocate(sorted)
  end function cvar

end module trend_stats
