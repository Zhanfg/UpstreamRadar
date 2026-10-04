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
}
