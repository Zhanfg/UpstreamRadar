defmodule UpstreamRadar.RadarWindow do
  @moduledoc "Deterministically reduces normalized radar events into repository windows."

  def reduce(events) when is_list(events) do
    events
    |> Enum.group_by(&Map.fetch!(&1, "repository"))
    |> Enum.map(fn {repository, items} ->
      %{
        repository: repository,
        events: length(items),
        max_impact: items |> Enum.map(&impact/1) |> Enum.max(fn -> 0.0 end),
        latest_observed_at: items |> Enum.map(&Map.get(&1, "observed_at", "")) |> Enum.max(fn -> "" end)
      }
    end)
    |> Enum.sort_by(fn item -> {-item.max_impact, -item.events, item.repository} end)
  end

  def surprise(empirical, predicted) when is_number(empirical) and is_number(predicted) do
    eps = 1.0e-12
    q = empirical |> max(eps) |> min(1.0 - eps)
    p = predicted |> max(eps) |> min(1.0 - eps)
    kl = q * :math.log(q / p) + (1.0 - q) * :math.log((1.0 - q) / (1.0 - p))
    1.0 - :math.exp(-3.4 * kl)
  end

  def cvar(values, quantile \\ 0.75) when is_list(values) do
    case Enum.sort(Enum.map(values, &min(1.0, max(0.0, &1 * 1.0)))) do
      [] -> 0.0
      xs ->
        q = min(0.999999, max(0.5, quantile))
        start = min(length(xs) - 1, trunc(Float.floor(length(xs) * q)))
        tail = Enum.drop(xs, start)
        Enum.sum(tail) / length(tail)
    end
  end

  defp impact(event) do
    case Map.get(event, "semantic_impact", 0.0) do
      value when is_number(value) -> value * 1.0
      _ -> 0.0
    end
  end
end
