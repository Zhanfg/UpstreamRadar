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
