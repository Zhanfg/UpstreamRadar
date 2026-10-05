(defpackage :upstreamradar.event-dedupe
  (:use :cl)
  (:export :deduplicate-events :pareto-frontier :risk-adjusted-utility))

(in-package :upstreamradar.event-dedupe)

(defun event-key (event)
  (list (getf event :source)
        (getf event :repository)
        (getf event :event-type)
        (getf event :observed-at)))

(defun deduplicate-events (events)
  "Keep the highest-impact event for each normalized event identity."
  (let ((table (make-hash-table :test #'equal)))
    (dolist (event events)
      (let* ((key (event-key event))
             (existing (gethash key table))
             (impact (or (getf event :semantic-impact) 0.0))
             (existing-impact (if existing
                                  (or (getf existing :semantic-impact) 0.0)
                                  -1.0)))
        (when (> impact existing-impact)
          (setf (gethash key table) event))))
    (let ((result '()))
      (maphash (lambda (_ event)
                 (declare (ignore _))
                 (push event result))
               table)
      (sort result
            (lambda (a b)
              (> (or (getf a :semantic-impact) 0.0)
                 (or (getf b :semantic-impact) 0.0)))))))


(defun dominates-p (left right)
  (let ((lu (or (getf left :utility) 0.0))
        (ln (or (getf left :structural-novelty) 0.0))
        (lr (or (getf left :tail-risk) 1.0))
        (ru (or (getf right :utility) 0.0))
        (rn (or (getf right :structural-novelty) 0.0))
        (rr (or (getf right :tail-risk) 1.0)))
    (and (>= lu ru)
         (>= ln rn)
         (<= lr rr)
         (or (> lu ru) (> ln rn) (< lr rr)))))

(defun pareto-frontier (items)
  (remove-if
   (lambda (candidate)
     (some (lambda (other)
             (and (not (eq candidate other))
                  (dominates-p other candidate)))
           items))
   items))

(defun risk-adjusted-utility (utility tail-risk reliability)
  (* (max 0.0 utility)
     (- 1.0 (* 0.11 (max 0.0 (min 1.0 tail-risk))))
     (+ 0.82 (* 0.18 (max 0.0 (min 1.0 reliability))))))
