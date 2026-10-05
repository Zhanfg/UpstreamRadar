unit Ewma;

{$mode objfpc}{$H+}

interface

uses
  SysUtils, Math;

type
  TDoubleArray = array of Double;

function ComputeEwma(const Values: TDoubleArray; Alpha: Double): TDoubleArray;
function BayesianSurprise(Empirical, Predicted: Double): Double;
function CVaR(const Values: TDoubleArray; Quantile: Double): Double;

implementation

function ComputeEwma(const Values: TDoubleArray; Alpha: Double): TDoubleArray;
var
  I: Integer;
begin
  if (Alpha <= 0.0) or (Alpha > 1.0) then
    raise Exception.Create('alpha must be in (0, 1]');

  SetLength(Result, Length(Values));
  if Length(Values) = 0 then
    Exit;

  Result[0] := Values[0];
  for I := 1 to High(Values) do
    Result[I] := Alpha * Values[I] + (1.0 - Alpha) * Result[I - 1];
end;

function Clamp01(Value: Double): Double;
begin
  if Value < 0.0 then Exit(0.0);
  if Value > 1.0 then Exit(1.0);
  Result := Value;
end;

function BayesianSurprise(Empirical, Predicted: Double): Double;
const
  Eps = 1.0E-12;
var
  Q, P, KL: Double;
begin
  Q := EnsureRange(Empirical, Eps, 1.0 - Eps);
  P := EnsureRange(Predicted, Eps, 1.0 - Eps);
  KL := Q * Ln(Q / P) + (1.0 - Q) * Ln((1.0 - Q) / (1.0 - P));
  Result := Clamp01(1.0 - Exp(-3.4 * KL));
end;

function CVaR(const Values: TDoubleArray; Quantile: Double): Double;
var
  Sorted: TDoubleArray;
  I, J, StartIndex: Integer;
  Temp, Sum, Q: Double;
begin
  if Length(Values) = 0 then Exit(0.0);
  SetLength(Sorted, Length(Values));
  for I := 0 to High(Values) do Sorted[I] := Clamp01(Values[I]);
  for I := 0 to High(Sorted) - 1 do
    for J := I + 1 to High(Sorted) do
      if Sorted[J] < Sorted[I] then
      begin
        Temp := Sorted[I];
        Sorted[I] := Sorted[J];
        Sorted[J] := Temp;
      end;
  Q := EnsureRange(Quantile, 0.5, 0.999999);
  StartIndex := Min(High(Sorted), Floor(Length(Sorted) * Q));
  Sum := 0.0;
  for I := StartIndex to High(Sorted) do Sum := Sum + Sorted[I];
  Result := Sum / (Length(Sorted) - StartIndex);
end;

end.
