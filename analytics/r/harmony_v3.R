clamp01 <- function(x) pmax(0, pmin(1, x))

bernoulli_kl <- function(q, p, eps = 1e-12) {
  q <- pmax(eps, pmin(1 - eps, q))
  p <- pmax(eps, pmin(1 - eps, p))
  q * log(q / p) + (1 - q) * log((1 - q) / (1 - p))
}

bayesian_surprise <- function(empirical, predicted) {
  clamp01(1 - exp(-3.4 * bernoulli_kl(empirical, predicted)))
}

cvar <- function(x, quantile = 0.75) {
  if (length(x) == 0) return(0)
  values <- sort(clamp01(x))
  start <- floor((length(values) - 1) * max(0.5, min(0.999999, quantile))) + 1
  mean(values[start:length(values)])
}

change_ensemble <- function(x, page_hinkley = 0) {
  if (length(x) < 2) return(clamp01(page_hinkley))
  prior <- x[-length(x)]
  center <- median(prior)
  mad_scale <- max(median(abs(prior - center)) * 1.4826, 1e-6)
  jump <- clamp01(abs(tail(x, 1) - center) / (1.35 * mad_scale))
  slope <- coef(lm(x ~ seq_along(x)))[2]
  slope_signal <- clamp01(abs(slope) * 4)
  clamp01(0.5 * page_hinkley + 0.3 * jump + 0.2 * slope_signal)
}
