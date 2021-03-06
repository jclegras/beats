// Copyright 2018 Elasticsearch Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package darwin

import (
	"syscall"

	"github.com/pkg/errors"
)

const hardwareMIB = "hw.machine"

func Architecture() (string, error) {
	arch, err := syscall.Sysctl(hardwareMIB)
	if err != nil {
		return "", errors.Wrap(err, "failed to get architecture")
	}

	return arch, nil
}
