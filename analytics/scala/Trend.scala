package upstreamradar.analytics

object Trend {
  def slope(values: IndexedSeq[Double]): Double = {
    if (values.length < 2) return 0.0
    val n = values.length.toDouble
    val meanX = (n - 1.0) / 2.0
    val meanY = values.sum / n
    var numerator = 0.0
    var denominator = 0.0
    values.indices.foreach { i =>
      val dx = i.toDouble - meanX
      numerator += dx * (values(i) - meanY)
      denominator += dx * dx
    }
    if (denominator == 0.0) 0.0 else numerator / denominator
  }

  private def clamp01(value: Double): Double = math.max(0.0, math.min(1.0, value))

  def ewma(values: IndexedSeq[Double], alpha: Double): Double = {
    require(alpha > 0.0 && alpha <= 1.0)
    values.headOption match {
      case None => 0.0
      case Some(first) =>
        values.tail.foldLeft(first) { (state, value) =>
          (1.0 - alpha) * state + alpha * value
        }
    }
  }

  def bernoulliKL(q0: Double, p0: Double): Double = {
    val eps = 1e-12
    val q = math.max(eps, math.min(1.0 - eps, q0))
    val p = math.max(eps, math.min(1.0 - eps, p0))
    q * math.log(q / p) + (1.0 - q) * math.log((1.0 - q) / (1.0 - p))
  }

  def bayesianSurprise(empirical: Double, predicted: Double): Double =
    clamp01(1.0 - math.exp(-3.4 * bernoulliKL(empirical, predicted)))

  def cvar(values: IndexedSeq[Double], quantile: Double = 0.75): Double = {
    if (values.isEmpty) return 0.0
    val sorted = values.map(clamp01).sorted
    val q = math.max(0.5, math.min(0.999999, quantile))
    val start = math.min(sorted.length - 1, math.floor(sorted.length.toDouble * q).toInt)
    sorted.drop(start).sum / (sorted.length - start)
  }

}
