with Ada.Text_IO; use Ada.Text_IO;
with Ada.Numerics.Elementary_Functions; use Ada.Numerics.Elementary_Functions;

procedure Radar_Policy is
   function Clamp (Value : Float) return Float is
   begin
      if Value < 0.0 then
         return 0.0;
      elsif Value > 1.0 then
         return 1.0;
      else
         return Value;
      end if;
   end Clamp;

   function Bayesian_Surprise (Empirical, Predicted : Float) return Float is
      Eps : constant Float := 1.0E-6;
      Q : constant Float := Float'Max (Eps, Float'Min (1.0 - Eps, Empirical));
      P : constant Float := Float'Max (Eps, Float'Min (1.0 - Eps, Predicted));
      KL : constant Float :=
        Q * Log (Q / P) + (1.0 - Q) * Log ((1.0 - Q) / (1.0 - P));
   begin
      return Clamp (1.0 - Exp (-3.4 * KL));
   end Bayesian_Surprise;

   function Risk_Adjusted (Utility, Tail_Risk, Reliability : Float) return Float is
   begin
      return Float'Max (0.0, Utility)
        * (1.0 - 0.11 * Clamp (Tail_Risk))
        * (0.82 + 0.18 * Clamp (Reliability));
   end Risk_Adjusted;

   function Classify (Impact, Security : Float) return String is
      I : constant Float := Clamp (Impact);
      S : constant Float := Clamp (Security);
      Combined : constant Float := 0.65 * I + 0.35 * S;
   begin
      if S >= 0.90 or else Combined >= 0.85 then
         return "critical";
      elsif Combined >= 0.60 then
         return "investigate";
      elsif Combined >= 0.30 then
         return "observe";
      else
         return "quiet";
      end if;
   end Classify;

begin
   Put_Line (Classify (0.72, 0.40));
end Radar_Policy;
