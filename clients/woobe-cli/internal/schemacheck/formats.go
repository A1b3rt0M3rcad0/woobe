package schemacheck

import (
	"regexp"
	"strings"
	"time"
)

var uuidPattern = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)
var dateTimePattern = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?([Zz]|[+-]([01][0-9]|2[0-3]):[0-5][0-9])$`)
var datePattern = regexp.MustCompile(`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`)

func supportedFormat(name string) bool {
	return name == "uuid" || name == "date-time" || name == "date"
}

func formatOK(name, value string) bool {
	switch name {
	case "uuid":
		return uuidPattern.MatchString(value)
	case "date":
		if !datePattern.MatchString(value) {
			return false
		}
		_, e := time.Parse("2006-01-02", value)
		return e == nil
	case "date-time":
		if !dateTimePattern.MatchString(value) {
			return false
		}
		value = strings.ToUpper(value)
		// RFC 3339 allows leap seconds. Check the corresponding UTC minute;
		// Go's parser rejects :60 and normalizes invalid timezone offsets.
		leap := value[17:19] == "60"
		if leap {
			value = value[:17] + "59" + value[19:]
		}
		t, e := time.Parse(time.RFC3339Nano, value)
		return e == nil && (!leap || t.UTC().Hour() == 23 && t.UTC().Minute() == 59)
	}
	return false
}
