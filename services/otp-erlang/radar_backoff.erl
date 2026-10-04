-module(radar_backoff).
-export([delay_ms/3]).

-spec delay_ms(non_neg_integer(), pos_integer(), pos_integer()) -> pos_integer().
delay_ms(Failures, BaseMs, CapMs)
  when is_integer(Failures), Failures >= 0,
       is_integer(BaseMs), BaseMs > 0,
       is_integer(CapMs), CapMs > 0 ->
    Shift = erlang:min(Failures, 20),
    Raw = BaseMs * (1 bsl Shift),
    erlang:min(Raw, CapMs).
