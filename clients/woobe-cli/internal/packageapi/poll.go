package packageapi

import (
	"context"
	"errors"
	"math/rand/v2"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

// Wait uses the caller's total deadline, including each HTTP request. Only GET
// observations are retried; acceptance, resume and cancellation are never replayed.
func (c *Client) Wait(ctx context.Context, initial Operation, observe func(Operation) error) (Operation, error) {
	current := initial
	backoff := 2 * time.Second
	for !current.Terminal {
		if err := ctx.Err(); err != nil {
			return current, output.Normalize(err)
		}
		pause := packagePollDelay(current.NextPollAfterMS, backoff)
		if current.NextPollAfterMS <= 0 && backoff < 15*time.Second {
			backoff *= 2
			if backoff > 15*time.Second {
				backoff = 15 * time.Second
			}
		}
		timer := time.NewTimer(pause)
		select {
		case <-ctx.Done():
			timer.Stop()
			return current, output.Normalize(ctx.Err())
		case <-timer.C:
		}
		next, err := c.Status(ctx, current.OperationID)
		if err != nil {
			if ctx.Err() != nil {
				return current, output.Normalize(ctx.Err())
			}
			var failure *output.Error
			if errors.As(err, &failure) && (failure.Code == 7 || failure.Code == 8) {
				continue
			}
			return current, err
		}
		if next.Revision < current.Revision || next.ArtifactDigest != current.ArtifactDigest {
			return current, output.New(9, "Package operation evidence regressed or changed identity")
		}
		current = next
		if observe != nil {
			if err := observe(current); err != nil {
				return current, err
			}
		}
	}
	return current, nil
}

func packagePollDelay(suggestedMS int64, backoff time.Duration) time.Duration {
	if suggestedMS > 0 {
		const maximum = time.Duration(1<<63 - 1)
		if suggestedMS > int64(maximum/time.Millisecond) {
			return maximum
		}
		return time.Duration(suggestedMS) * time.Millisecond
	}
	// Jitter only the local fallback; an advertised delay is authoritative.
	floor, ceiling := backoff-backoff/5, backoff+backoff/5
	if floor < 2*time.Second {
		floor = 2 * time.Second
	}
	if ceiling > 15*time.Second {
		ceiling = 15 * time.Second
	}
	if ceiling <= floor {
		return floor
	}
	return floor + time.Duration(rand.Int64N(int64(ceiling-floor)+1))
}
