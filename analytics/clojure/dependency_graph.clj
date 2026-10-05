(ns upstreamradar.dependency-graph)

(defn reachable
  "Return the transitive dependency closure from start, excluding start."
  [graph start]
  (loop [stack (seq (get graph start #{}))
         seen #{}]
    (if (empty? stack)
      seen
      (let [node (first stack)
            rest-stack (rest stack)]
        (if (contains? seen node)
          (recur rest-stack seen)
          (recur (concat (get graph node #{}) rest-stack)
                 (conj seen node)))))))

(defn blast-radius
  "Number of unique dependencies reachable from start."
  [graph start]
  (count (reachable graph start)))


(defn personalized-rank
  "Deterministic seeded graph diffusion with dangling redistribution."
  [graph seeds damping steps]
  (let [nodes (set (concat (keys graph) (mapcat identity (vals graph))))
        total (max 1.0 (reduce + (map #(double (get seeds % 0.0)) nodes)))
        teleport (into {} (map (fn [n] [n (/ (double (get seeds n 0.0)) total)]) nodes))]
    (loop [rank teleport
           step 0]
      (if (>= step steps)
        rank
        (let [base (into {} (map (fn [n] [n (* (- 1.0 damping) (get teleport n 0.0))]) nodes))
              next-rank
              (reduce
                (fn [acc source]
                  (let [targets (seq (get graph source #{}))
                        weight (double (get rank source 0.0))]
                    (if targets
                      (let [share (/ (* damping weight) (count targets))]
                        (reduce #(update %1 %2 (fnil + 0.0) share) acc targets))
                      (reduce
                        (fn [m n]
                          (update m n (fnil + 0.0)
                                  (* damping weight (get teleport n 0.0))))
                        acc
                        nodes))))
                base
                nodes)]
          (recur next-rank (inc step)))))))

(defn structural-novelty
  "Rarity-weighted dependency novelty in [0,1]."
  [graph node]
  (let [deps (set (get graph node #{}))]
    (if (empty? deps)
      0.0
      (let [frequency
            (frequencies (mapcat identity (vals graph)))
            rarity (/ (reduce + (map #(/ 1.0 (max 1 (get frequency % 1))) deps))
                      (count deps))
            breadth (- 1.0 (Math/exp (/ (- (count deps)) 3.0)))]
        (min 1.0 (+ (* 0.6 rarity) (* 0.4 breadth)))))))
