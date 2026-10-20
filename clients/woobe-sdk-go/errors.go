package woobe

import "fmt"

type RequestError struct {
	StatusCode int
	Message    string
	Body       string
}

func (e *RequestError) Error() string {
	if e.StatusCode > 0 {
		return fmt.Sprintf("woobe request failed (%d): %s", e.StatusCode, e.Message)
	}
	return e.Message
}
func (e *RequestError) Retryable() bool {
	return e.StatusCode == 0 || e.StatusCode == 408 || e.StatusCode == 409 || e.StatusCode == 425 || e.StatusCode == 429 || e.StatusCode >= 500
}

type AuthenticationError struct{ *RequestError }

type ConnectionError struct {
	Message string
	Cause   error
}
func (e *ConnectionError) Error() string {
	if e.Cause != nil { return e.Message + ": " + e.Cause.Error() }
	return e.Message
}
func (e *ConnectionError) Unwrap() error { return e.Cause }

type ProtocolError struct {
	Message string
	Cause   error
}
func (e *ProtocolError) Error() string {
	if e.Cause != nil { return e.Message + ": " + e.Cause.Error() }
	return e.Message
}
func (e *ProtocolError) Unwrap() error { return e.Cause }

type RecoveryError struct {
	Message string
	Cause   error
}
func (e *RecoveryError) Error() string {
	if e.Cause != nil { return e.Message + ": " + e.Cause.Error() }
	return e.Message
}
func (e *RecoveryError) Unwrap() error { return e.Cause }

type StreamGapError struct{ Expected, Received int64 }
func (e *StreamGapError) Error() string {
	return fmt.Sprintf("runtime event sequence gap: expected %d, received %d", e.Expected, e.Received)
}
