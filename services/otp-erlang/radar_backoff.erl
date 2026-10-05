-module(radar_backoff).
-export([delay_ms/3, delay_ms/4, failure_risk/1]).

-spec delay_ms(non_neg_integer(), pos_integer(), pos_integer()) -> pos_integer().
delay_ms(Failures, BaseMs, CapMs)
  when is_integer(Failures), Failures >= 0,
       is_integer(BaseMs), BaseMs > 0,
       is_integer(CapMs), CapMs > 0 ->
    Shift = erlang:min(Failures, 20),
    Raw = BaseMs * (1 bsl Shift),
    erlang:min(Raw, CapMs).


-spec failure_risk(non_neg_integer()) -> float().
failure_risk(Failures) when is_integer(Failures), Failures >= 0 ->
    1.0 - math:exp(-0.28 * Failures).

-spec delay_ms(non_neg_integer(), pos_integer(), pos_integer(), binary()) -> pos_integer().
delay_ms(Failures, BaseMs, CapMs, Key)
  when is_binary(Key) ->
    Base = delay_ms(Failures, BaseMs, CapMs),
    %% Deterministic jitter keeps retries de-synchronized without random tests.
    Hash = erlang:phash2({Key, Failures}, 1001),
    Jitter = 0.85 + (Hash / 1000.0) * 0.30,
    erlang:min(CapMs, erlang:max(1, round(Base * Jitter))).
