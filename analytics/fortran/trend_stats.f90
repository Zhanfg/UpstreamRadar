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

end module trend_stats
