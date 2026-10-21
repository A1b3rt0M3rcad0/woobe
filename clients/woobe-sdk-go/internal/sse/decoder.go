package sse

import "strings"

type Frame struct {
	Event string
	ID    string
	Data  []byte
}

type Decoder struct {
	event string
	id    string
	data  []string
}

func NewDecoder() *Decoder { return &Decoder{} }

func (d *Decoder) Feed(line string) *Frame {
	if line == "" {
		return d.flush()
	}
	if strings.HasPrefix(line, ":") {
		return nil
	}
	field, val, ok := strings.Cut(line, ":")
	if ok && strings.HasPrefix(val, " ") {
		val = val[1:]
	}
	switch field {
	case "event":
		d.event = val
	case "id":
		d.id = val
	case "data":
		d.data = append(d.data, val)
	}
	return nil
}

func (d *Decoder) Finish() *Frame { return d.flush() }

func (d *Decoder) flush() *Frame {
	if len(d.data) == 0 {
		d.event, d.id = "", ""
		return nil
	}
	f := &Frame{Event: d.event, ID: d.id, Data: []byte(strings.Join(d.data, "\n"))}
	d.event, d.id, d.data = "", "", nil
	return f
}
