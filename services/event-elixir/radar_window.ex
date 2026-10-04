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

  defp impact(event) do
    case Map.get(event, "semantic_impact", 0.0) do
      value when is_number(value) -> value * 1.0
      _ -> 0.0
    end
  end
end
