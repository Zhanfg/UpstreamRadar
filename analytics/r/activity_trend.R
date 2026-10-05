ewma <- function(x, alpha = 0.3) {
  stopifnot(length(alpha) == 1, alpha > 0, alpha <= 1)
  if (length(x) == 0) return(numeric())
  out <- numeric(length(x))
  out[1] <- x[1]
  if (length(x) > 1) {
    for (i in 2:length(x)) {
      out[i] <- alpha * x[i] + (1 - alpha) * out[i - 1]
    }
  }
  out
}

robust_z <- function(x) {
  if (length(x) == 0) return(numeric())
  center <- median(x)
  scale <- median(abs(x - center))
  if (scale == 0) return(rep(0, length(x)))
  0.67448975 * (x - center) / scale
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) > 0) {
  values <- as.numeric(args)
  result <- data.frame(value = values, ewma = ewma(values), robust_z = robust_z(values))
  write.csv(result, stdout(), row.names = FALSE)
}
