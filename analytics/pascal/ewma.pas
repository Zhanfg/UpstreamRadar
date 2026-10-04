unit Ewma;

{$mode objfpc}{$H+}

interface

type
  TDoubleArray = array of Double;

function ComputeEwma(const Values: TDoubleArray; Alpha: Double): TDoubleArray;

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

end.
