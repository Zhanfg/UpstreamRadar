with Ada.Text_IO; use Ada.Text_IO;

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
