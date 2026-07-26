(function () {
    const pageData = window.pageData || {};
    const form = document.getElementById("registerForm");
    const verifyForm = document.getElementById("verifyRegisterForm");
    const registerButton = document.getElementById("registerButton");
    const verifyRegisterButton = document.getElementById("verifyRegisterButton");
    const registerMessage = document.getElementById("registerMessage");
    const verifyRegisterMessage = document.getElementById("verifyRegisterMessage");
    const userIdInput = document.getElementById("user_id");
    const emailDomainInput = document.getElementById("email_domain");
    const emailPreview = document.getElementById("emailPreview");
    const passwordInput = document.getElementById("password");
    const confirmPasswordInput = document.getElementById("confirm_hzn");
    const passwordFeedback = document.getElementById("passwordFeedback");
    const passwordMatchFeedback = document.getElementById("passwordMatchFeedback");
    const otpInputs = Array.prototype.slice.call(document.querySelectorAll(".otp-input"));
    const otpModalElement = document.getElementById("registerOtpModal");
    const otpModal = otpModalElement ? new bootstrap.Modal(otpModalElement) : null;
    let registerTimeoutId = null;

    function parseJsonResponse(response) {
        return response.text().then(function (text) {
            let data = {};
            if (text) {
                try {
                    data = JSON.parse(text);
                } catch (error) {
                    data = { error: "Server returned an invalid response." };
                }
            }
            return { ok: response.ok, data: data };
        });
    }

    function setAlertState(element, type, message) {
        if (!element) {
            return;
        }
        if (!message) {
            element.className = "alert d-none";
            element.textContent = "";
            return;
        }
        element.className = "alert alert-" + type;
        element.textContent = message;
    }

    function setRuleState(ruleName, isValid) {
        const rule = document.querySelector('[data-rule="' + ruleName + '"]');
        if (!rule) {
            return;
        }

        const icon = rule.querySelector("i");
        rule.classList.toggle("is-valid", isValid);
        rule.classList.toggle("is-invalid", !isValid);
        if (icon) {
            icon.className = isValid
                ? "fas fa-check-circle text-success"
                : "fas fa-times-circle text-danger";
        }
    }

    function getPasswordRules(password) {
        const value = String(password || "");
        return {
            length: value.length >= 8,
            uppercase: /[A-Z]/.test(value),
            lowercase: /[a-z]/.test(value),
            digit: /\d/.test(value),
            symbol: /[@$!%*?&]/.test(value),
        };
    }

    function passwordRulesPassed(rules) {
        return Object.keys(rules).every(function (key) {
            return rules[key];
        });
    }

    function setFeedbackState(element, message, isValid) {
        if (!element) {
            return;
        }
        element.textContent = message || "";
        element.classList.toggle("text-success", Boolean(message) && isValid);
        element.classList.toggle("text-danger", Boolean(message) && !isValid);
    }

    function sanitizeDomain(value) {
        const normalizedValue = String(value || "").trim().toLowerCase().replace(/^@+/, "");
        if (!normalizedValue) {
            return "";
        }
        if (normalizedValue.indexOf(".") === -1) {
            return normalizedValue + ".com";
        }
        return normalizedValue;
    }

    function buildEmailPreview() {
        const username = String(userIdInput ? userIdInput.value : "").trim().toLowerCase();
        const domain = sanitizeDomain(emailDomainInput ? emailDomainInput.value : "");

        if (!username) {
            return "Enter a user ID to preview the email address.";
        }
        if (!domain) {
            return "Select a domain to preview the email address.";
        }
        return username + "@" + domain;
    }

    function updateEmailPreview() {
        if (emailPreview) {
            emailPreview.textContent = buildEmailPreview();
        }
    }

    function updateFormState() {
        const password = passwordInput ? passwordInput.value : "";
        const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";
        const rules = getPasswordRules(password);
        const strongPassword = passwordRulesPassed(rules);
        const passwordsMatch = Boolean(password) && password === confirmPassword;
        const hasUserId = Boolean(String(userIdInput ? userIdInput.value : "").trim());
        const hasDomain = Boolean(String(emailDomainInput ? emailDomainInput.value : "").trim());

        Object.keys(rules).forEach(function (ruleName) {
            setRuleState(ruleName, rules[ruleName]);
        });

        if (!password) {
            setFeedbackState(passwordFeedback, "", false);
        } else if (strongPassword) {
            setFeedbackState(passwordFeedback, "Strong password.", true);
        } else {
            setFeedbackState(passwordFeedback, "Use all password requirements before continuing.", false);
        }

        if (!confirmPassword) {
            setFeedbackState(passwordMatchFeedback, "", false);
        } else if (passwordsMatch) {
            setFeedbackState(passwordMatchFeedback, "Passwords match.", true);
        } else {
            setFeedbackState(passwordMatchFeedback, "Passwords do not match.", false);
        }

        if (registerButton) {
            registerButton.disabled = !(strongPassword && passwordsMatch && hasUserId && hasDomain);
        }
    }

    function clearOtpInputs() {
        otpInputs.forEach(function (input) {
            input.value = "";
        });
        if (otpInputs[0]) {
            otpInputs[0].focus();
        }
    }

    function getOtpCode() {
        return otpInputs.map(function (input) {
            return String(input.value || "").trim();
        }).join("");
    }

    function clearVerificationTimeout() {
        if (registerTimeoutId) {
            window.clearTimeout(registerTimeoutId);
            registerTimeoutId = null;
        }
    }

    function startVerificationTimeout() {
        clearVerificationTimeout();
        registerTimeoutId = window.setTimeout(function () {
            setAlertState(
                verifyRegisterMessage,
                "warning",
                "Verification timed out after 2 minutes. Please start registration again."
            );
            if (verifyRegisterButton) {
                verifyRegisterButton.disabled = true;
            }
        }, 120000);
    }

    function redirectAfterSuccess() {
        window.setTimeout(function () {
            window.location.href = pageData.successRedirectUrl || "/login";
        }, 900);
    }

    function attachOtpInputBehavior() {
        otpInputs.forEach(function (input, index) {
            input.addEventListener("input", function () {
                const sanitizedValue = String(input.value || "").replace(/\D/g, "").slice(0, 1);
                input.value = sanitizedValue;

                if (sanitizedValue && index < otpInputs.length - 1) {
                    otpInputs[index + 1].focus();
                }
            });

            input.addEventListener("keydown", function (event) {
                if (event.key === "Backspace" && !input.value && index > 0) {
                    otpInputs[index - 1].focus();
                }
                if (event.key === "ArrowLeft" && index > 0) {
                    otpInputs[index - 1].focus();
                }
                if (event.key === "ArrowRight" && index < otpInputs.length - 1) {
                    otpInputs[index + 1].focus();
                }
            });

            input.addEventListener("paste", function (event) {
                const pasted = String((event.clipboardData || window.clipboardData).getData("text") || "")
                    .replace(/\D/g, "")
                    .slice(0, otpInputs.length);
                if (!pasted) {
                    return;
                }

                event.preventDefault();
                otpInputs.forEach(function (otpInput, otpIndex) {
                    otpInput.value = pasted[otpIndex] || "";
                });

                const focusIndex = Math.min(pasted.length, otpInputs.length) - 1;
                if (focusIndex >= 0) {
                    otpInputs[focusIndex].focus();
                }
            });
        });
    }

    function handleRegisterSubmit(event) {
        event.preventDefault();
        updateEmailPreview();
        updateFormState();

        if (registerButton && registerButton.disabled) {
            setAlertState(registerMessage, "danger", "Please complete the required fields and fix the password validation errors first.");
            return;
        }

        setAlertState(registerMessage, "", "");
        setAlertState(verifyRegisterMessage, "", "");
        registerButton.disabled = true;

        fetch(pageData.requestUrl, {
            method: "POST",
            body: new FormData(form),
            credentials: "same-origin",
        })
            .then(parseJsonResponse)
            .then(function (result) {
                if (!result.ok || !result.data.success) {
                    throw new Error(result.data.error || "Unable to start registration verification.");
                }

                clearOtpInputs();
                if (verifyRegisterButton) {
                    verifyRegisterButton.disabled = false;
                }
                setAlertState(
                    registerMessage,
                    "success",
                    "Verification code sent to " + (result.data.email_id || buildEmailPreview()) + "."
                );
                if (otpModal) {
                    otpModal.show();
                }
                startVerificationTimeout();
            })
            .catch(function (error) {
                setAlertState(registerMessage, "danger", error.message);
            })
            .finally(function () {
                updateFormState();
            });
    }

    function handleVerificationSubmit(event) {
        event.preventDefault();
        const code = getOtpCode();

        if (code.length !== 6) {
            setAlertState(verifyRegisterMessage, "danger", "Enter the full 6-digit verification code.");
            return;
        }

        setAlertState(verifyRegisterMessage, "", "");
        verifyRegisterButton.disabled = true;

        fetch(pageData.verifyUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            credentials: "same-origin",
            body: JSON.stringify({ code: code }),
        })
            .then(parseJsonResponse)
            .then(function (result) {
                if (!result.ok || !result.data.success) {
                    throw new Error(result.data.error || "Verification failed.");
                }

                clearVerificationTimeout();
                setAlertState(
                    verifyRegisterMessage,
                    "success",
                    "Registration completed successfully. Redirecting to login."
                );
                redirectAfterSuccess();
            })
            .catch(function (error) {
                setAlertState(verifyRegisterMessage, "danger", error.message);
                verifyRegisterButton.disabled = false;
            });
    }

    if (!form || !verifyForm) {
        return;
    }

    if (userIdInput) {
        userIdInput.addEventListener("input", function () {
            updateEmailPreview();
            updateFormState();
        });
    }

    if (emailDomainInput) {
        emailDomainInput.addEventListener("change", function () {
            updateEmailPreview();
            updateFormState();
        });
    }

    if (passwordInput) {
        passwordInput.addEventListener("input", updateFormState);
    }

    if (confirmPasswordInput) {
        confirmPasswordInput.addEventListener("input", updateFormState);
    }

    if (otpModalElement) {
        otpModalElement.addEventListener("hidden.bs.modal", function () {
            setAlertState(verifyRegisterMessage, "", "");
            clearOtpInputs();
        });
    }

    form.addEventListener("submit", handleRegisterSubmit);
    verifyForm.addEventListener("submit", handleVerificationSubmit);
    attachOtpInputBehavior();
    updateEmailPreview();
    updateFormState();
}());
