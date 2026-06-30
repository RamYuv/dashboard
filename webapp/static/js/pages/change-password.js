(function () {
    const pageData = window.pageData || {};
    const isForgotPassword = pageData.pageMode === "forgot-password";
    const form = document.getElementById("changePasswordForm");
    const verifyForm = document.getElementById("verifyPasswordForm");
    const changePasswordButton = document.getElementById("changePasswordButton");
    const verifyPasswordButton = document.getElementById("verifyPasswordButton");
    const changePasswordMessage = document.getElementById("changePasswordMessage");
    const verifyPasswordMessage = document.getElementById("verifyPasswordMessage");
    const newPasswordInput = document.getElementById("new_password");
    const confirmPasswordInput = document.getElementById("confirm_password");
    const otpInputs = Array.prototype.slice.call(document.querySelectorAll(".otp-input"));
    const passwordFeedback = document.getElementById("passwordFeedback");
    const passwordMatchFeedback = document.getElementById("passwordMatchFeedback");
    const otpModalElement = document.getElementById("passwordOtpModal");
    const otpModal = otpModalElement ? new bootstrap.Modal(otpModalElement) : null;
    let passwordChangeTimeoutId = null;

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

    function updateFormState() {
        const password = newPasswordInput ? newPasswordInput.value : "";
        const confirmPassword = confirmPasswordInput ? confirmPasswordInput.value : "";
        const rules = getPasswordRules(password);
        const strongPassword = passwordRulesPassed(rules);
        const passwordsMatch = Boolean(password) && password === confirmPassword;

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

        if (changePasswordButton) {
            changePasswordButton.disabled = !(strongPassword && passwordsMatch);
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

    function startVerificationTimeout() {
        clearVerificationTimeout();
        passwordChangeTimeoutId = window.setTimeout(function () {
            setAlertState(
                verifyPasswordMessage,
                "warning",
                isForgotPassword
                    ? "Verification timed out after 2 minutes. Please start the password reset again."
                    : "Verification timed out after 2 minutes. Please start the password change again."
            );
            if (verifyPasswordButton) {
                verifyPasswordButton.disabled = true;
            }
        }, 120000);
    }

    function clearVerificationTimeout() {
        if (passwordChangeTimeoutId) {
            window.clearTimeout(passwordChangeTimeoutId);
            passwordChangeTimeoutId = null;
        }
    }

    function redirectAfterSuccess() {
        window.setTimeout(function () {
            window.location.href = pageData.successRedirectUrl || "/";
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

    function handleChangePasswordSubmit(event) {
        event.preventDefault();
        updateFormState();

        if (changePasswordButton && changePasswordButton.disabled) {
            setAlertState(changePasswordMessage, "danger", "Please fix the password validation errors first.");
            return;
        }

        setAlertState(changePasswordMessage, "", "");
        setAlertState(verifyPasswordMessage, "", "");
        changePasswordButton.disabled = true;

        fetch(pageData.requestUrl, {
            method: "POST",
            body: new FormData(form),
            credentials: "same-origin",
        })
            .then(parseJsonResponse)
            .then(function (result) {
                if (!result.ok || !result.data.success) {
                    throw new Error(
                        result.data.error || (
                            isForgotPassword
                                ? "Unable to start forgot password verification."
                                : "Unable to start password change verification."
                        )
                    );
                }

                clearOtpInputs();
                if (verifyPasswordButton) {
                    verifyPasswordButton.disabled = false;
                }
                setAlertState(
                    changePasswordMessage,
                    "success",
                    "Verification code sent. Check your email and enter the code below."
                );
                if (otpModal) {
                    otpModal.show();
                }
                startVerificationTimeout();
            })
            .catch(function (error) {
                setAlertState(changePasswordMessage, "danger", error.message);
            })
            .finally(function () {
                updateFormState();
            });
    }

    function handleVerificationSubmit(event) {
        event.preventDefault();
        const code = getOtpCode();

        if (code.length !== 6) {
            setAlertState(verifyPasswordMessage, "danger", "Enter the full 6-digit verification code.");
            return;
        }

        setAlertState(verifyPasswordMessage, "", "");
        verifyPasswordButton.disabled = true;

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
                    verifyPasswordMessage,
                    "success",
                    isForgotPassword
                        ? "Password reset successfully. Redirecting to login."
                        : "Password changed successfully. Redirecting to your profile."
                );
                redirectAfterSuccess();
            })
            .catch(function (error) {
                setAlertState(verifyPasswordMessage, "danger", error.message);
                verifyPasswordButton.disabled = false;
            });
    }

    if (!form || !verifyForm) {
        return;
    }

    if (newPasswordInput) {
        newPasswordInput.addEventListener("input", updateFormState);
    }
    if (confirmPasswordInput) {
        confirmPasswordInput.addEventListener("input", updateFormState);
    }

    if (otpModalElement) {
        otpModalElement.addEventListener("hidden.bs.modal", function () {
            setAlertState(verifyPasswordMessage, "", "");
            clearOtpInputs();
        });
    }

    form.addEventListener("submit", handleChangePasswordSubmit);
    verifyForm.addEventListener("submit", handleVerificationSubmit);
    attachOtpInputBehavior();
    updateFormState();
}());
