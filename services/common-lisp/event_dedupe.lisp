(defpackage :upstreamradar.event-dedupe
  (:use :cl)
  (:export :deduplicate-events))

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
