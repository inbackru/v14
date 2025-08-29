// Modal Management Functions

function openQuizModal() {
    const modal = document.getElementById('quiz-modal-container');
    const content = document.getElementById('quiz-content');
    
    // Load quiz content
    fetch('/quiz-registration')
        .then(response => response.text())
        .then(html => {
            // Extract only the content part without full page structure
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const quizContent = doc.querySelector('#quiz-container');
            
            if (quizContent) {
                content.innerHTML = quizContent.outerHTML;
                
                // Re-initialize quiz functionality
                initQuizInModal();
                
                // Show modal
                modal.classList.remove('hidden');
                setTimeout(() => {
                    modal.querySelector('.relative').classList.add('scale-100');
                    modal.querySelector('.relative').classList.remove('scale-95');
                }, 10);
                
                // Prevent body scroll
                document.body.style.overflow = 'hidden';
            } else {
                console.error('Quiz content not found');
            }
        })
        .catch(error => {
            console.error('Error loading quiz:', error);
            content.innerHTML = '<div class="p-8 text-center"><p class="text-red-600">Ошибка загрузки формы. Попробуйте позже.</p></div>';
            modal.classList.remove('hidden');
        });
}

function closeQuizModal() {
    const modal = document.getElementById('quiz-modal-container');
    
    modal.querySelector('.relative').classList.add('scale-95');
    modal.querySelector('.relative').classList.remove('scale-100');
    
    setTimeout(() => {
        modal.classList.add('hidden');
        document.body.style.overflow = 'auto';
    }, 300);
}

function openCallbackModal() {
    const modal = document.getElementById('callback-modal-container');
    const content = document.getElementById('callback-content');
    
    // Load callback content
    fetch('/callback-request')
        .then(response => response.text())
        .then(html => {
            // Extract only the content part without full page structure
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const callbackContent = doc.querySelector('#callback-container');
            
            if (callbackContent) {
                content.innerHTML = callbackContent.outerHTML;
                
                // Re-initialize callback functionality
                initCallbackInModal();
                
                // Show modal
                modal.classList.remove('hidden');
                setTimeout(() => {
                    modal.querySelector('.relative').classList.add('scale-100');
                    modal.querySelector('.relative').classList.remove('scale-95');
                }, 10);
                
                // Prevent body scroll
                document.body.style.overflow = 'hidden';
            } else {
                console.error('Callback content not found');
            }
        })
        .catch(error => {
            console.error('Error loading callback form:', error);
            content.innerHTML = '<div class="p-8 text-center"><p class="text-red-600">Ошибка загрузки формы. Попробуйте позже.</p></div>';
            modal.classList.remove('hidden');
        });
}

function closeCallbackModal() {
    const modal = document.getElementById('callback-modal-container');
    
    modal.querySelector('.relative').classList.add('scale-95');
    modal.querySelector('.relative').classList.remove('scale-100');
    
    setTimeout(() => {
        modal.classList.add('hidden');
        document.body.style.overflow = 'auto';
    }, 300);
}

function initQuizInModal() {
    // Re-initialize quiz step functionality for modal
    let currentQuizStep = 1;
    const totalQuizSteps = 5;
    let quizData = {
        district: '',
        property_type: '',
        room_count: '',
        budget: ''
    };
    
    // Global functions for modal quiz
    window.selectOption = function(element, category) {
        // Remove selection from siblings
        const siblings = element.parentNode.querySelectorAll('.option-card');
        siblings.forEach(sibling => sibling.classList.remove('selected'));
        
        // Add selection to current
        element.classList.add('selected');
        
        // Store selection
        quizData[category] = element.dataset.value;
        
        // Enable next button
        const nextBtn = document.getElementById('nextBtn');
        if (nextBtn) {
            nextBtn.disabled = false;
            nextBtn.classList.remove('opacity-50');
        }
    };
    
    window.nextStep = function() {
        if (currentQuizStep < totalQuizSteps) {
            // Hide current step
            const currentStepEl = document.getElementById(`quiz-step-${currentQuizStep}`);
            if (currentStepEl) {
                currentStepEl.classList.add('hidden');
            }
            
            // Update step indicator
            const currentIndicator = document.getElementById(`step-${currentQuizStep}`);
            if (currentIndicator) {
                currentIndicator.classList.remove('step-active');
                currentIndicator.classList.add('step-completed');
            }
            
            // Show next step
            currentQuizStep++;
            const nextStepEl = document.getElementById(`quiz-step-${currentQuizStep}`);
            if (nextStepEl) {
                nextStepEl.classList.remove('hidden');
            }
            
            const nextIndicator = document.getElementById(`step-${currentQuizStep}`);
            if (nextIndicator) {
                nextIndicator.classList.remove('step-inactive');
                nextIndicator.classList.add('step-active');
            }
            
            // Update navigation
            updateQuizNavigation();
        }
    };
    
    window.previousStep = function() {
        if (currentQuizStep > 1) {
            // Hide current step
            const currentStepEl = document.getElementById(`quiz-step-${currentQuizStep}`);
            if (currentStepEl) {
                currentStepEl.classList.add('hidden');
            }
            
            // Update step indicator
            const currentIndicator = document.getElementById(`step-${currentQuizStep}`);
            if (currentIndicator) {
                currentIndicator.classList.remove('step-active');
                currentIndicator.classList.add('step-inactive');
            }
            
            // Show previous step
            currentQuizStep--;
            const prevStepEl = document.getElementById(`quiz-step-${currentQuizStep}`);
            if (prevStepEl) {
                prevStepEl.classList.remove('hidden');
            }
            
            const prevIndicator = document.getElementById(`step-${currentQuizStep}`);
            if (prevIndicator) {
                prevIndicator.classList.remove('step-completed');
                prevIndicator.classList.add('step-active');
            }
            
            // Update navigation
            updateQuizNavigation();
        }
    };
    
    window.submitRegistration = function() {
        const form = document.getElementById('registrationForm');
        if (!form) return;
        
        const formData = new FormData(form);
        
        // Validate form
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // No password check needed for application
        
        // Show loading
        const submitText = document.getElementById('submitText');
        const submitSpinner = document.getElementById('submitSpinner');
        const submitBtn = document.getElementById('submitBtn');
        
        if (submitText) submitText.classList.add('hidden');
        if (submitSpinner) submitSpinner.classList.remove('hidden');
        if (submitBtn) submitBtn.disabled = true;
        
        // Prepare application data
        const applicationData = {
            name: formData.get('full_name'),
            email: formData.get('email'),
            phone: formData.get('phone'),
            preferred_district: quizData.district,
            property_type: quizData.property_type,
            room_count: quizData.room_count,
            budget_range: quizData.budget,
            application_type: 'property_selection'
        };
        
        // Submit application
        fetch('/api/property-selection', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(applicationData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Заявка отправлена! Наш менеджер свяжется с вами с подходящими вариантами квартир.');
                closeQuizModal();
            } else {
                alert('Ошибка отправки заявки: ' + data.error);
                resetQuizSubmitButton();
            }
        })
        .catch(error => {
            console.error('Application error:', error);
            alert('Произошла ошибка. Попробуйте еще раз.');
            resetQuizSubmitButton();
        });
    };
    
    function resetQuizSubmitButton() {
        const submitText = document.getElementById('submitText');
        const submitSpinner = document.getElementById('submitSpinner');
        const submitBtn = document.getElementById('submitBtn');
        
        if (submitText) submitText.classList.remove('hidden');
        if (submitSpinner) submitSpinner.classList.add('hidden');
        if (submitBtn) submitBtn.disabled = false;
    }
    
    function updateQuizNavigation() {
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const submitBtn = document.getElementById('submitBtn');
        
        // Show/hide previous button
        if (prevBtn) {
            prevBtn.style.display = currentQuizStep > 1 ? 'block' : 'none';
        }
        
        // Show/hide next/submit buttons
        if (currentQuizStep === totalQuizSteps) {
            if (nextBtn) nextBtn.classList.add('hidden');
            if (submitBtn) submitBtn.classList.remove('hidden');
        } else {
            if (nextBtn) {
                nextBtn.classList.remove('hidden');
                nextBtn.disabled = true;
                nextBtn.classList.add('opacity-50');
            }
            if (submitBtn) submitBtn.classList.add('hidden');
        }
    }

    // Global functions
    window.openQuizModal = openQuizModal;
    window.closeQuizModal = closeQuizModal;
    window.submitRegistration = submitRegistration;
    window.openCallbackModal = openCallbackModal;
    window.closeCallbackModal = closeCallbackModal;
    
    function showQuizStep(step) {
        // Hide all steps
        for (let i = 1; i <= totalQuizSteps; i++) {
            const stepEl = document.getElementById(`quiz-step-${i}`);
            if (stepEl) {
                stepEl.classList.add('hidden');
            }
        }
        
        // Show current step
        const currentStepEl = document.getElementById(`quiz-step-${step}`);
        if (currentStepEl) {
            currentStepEl.classList.remove('hidden');
        }
        
        // Update navigation
        updateQuizNavigation();
    }
    
    function updateQuizProgress(step) {
        const progress = (step / totalQuizSteps) * 100;
        const progressBar = document.querySelector('#quiz-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        
        const stepText = document.querySelector('#quiz-step-text');
        if (stepText) {
            stepText.textContent = `Шаг ${step} из ${totalQuizSteps}`;
        }
    }
    
    // Next step handlers
    window.nextQuizStep = function(nextStep) {
        if (nextStep <= totalQuizSteps) {
            currentQuizStep = nextStep;
            showQuizStep(currentQuizStep);
        }
    }
    
    // Previous step handler
    window.prevQuizStep = function() {
        if (currentQuizStep > 1) {
            currentQuizStep--;
            showQuizStep(currentQuizStep);
        }
    }
    
    // Initialize first step
    showQuizStep(1);
    
    // Handle form submission
    const quizForm = document.getElementById('quiz-form');
    if (quizForm) {
        quizForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch('/api/submit-quiz', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message and close modal
                    alert('Спасибо! Мы подобрали для вас подходящие варианты квартир и сохранили ваши предпочтения.');
                    closeQuizModal();
                    
                    // Optionally redirect to properties or dashboard
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    }
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                console.error('Error submitting quiz:', error);
                alert('Произошла ошибка при отправке формы. Попробуйте позже.');
            });
        });
    }
}

function initCallbackInModal() {
    // Re-initialize callback step functionality for modal
    let currentCallbackStep = 1;
    const totalCallbackSteps = 4;
    let callbackData = {
        interest: '',
        budget: '',
        timing: ''
    };
    
    // Global functions for modal callback
    window.selectCallbackOption = function(element, category) {
        // Remove selection from siblings
        const siblings = element.parentNode.querySelectorAll('.option-card');
        siblings.forEach(sibling => sibling.classList.remove('selected'));
        
        // Add selection to current
        element.classList.add('selected');
        
        // Store selection
        callbackData[category] = element.dataset.value;
        
        // Enable next button
        const nextBtn = document.getElementById('callbackNextBtn');
        if (nextBtn) {
            nextBtn.disabled = false;
            nextBtn.classList.remove('opacity-50');
        }
    };
    
    window.nextCallbackStep = function() {
        if (currentCallbackStep < totalCallbackSteps) {
            // Hide current step
            const currentStepEl = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (currentStepEl) {
                currentStepEl.classList.add('hidden');
            }
            
            // Update step indicator
            const currentIndicator = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (currentIndicator) {
                currentIndicator.classList.remove('step-active');
                currentIndicator.classList.add('step-completed');
            }
            
            // Show next step
            currentCallbackStep++;
            const nextStepEl = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (nextStepEl) {
                nextStepEl.classList.remove('hidden');
            }
            
            const nextIndicator = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (nextIndicator) {
                nextIndicator.classList.remove('step-inactive');
                nextIndicator.classList.add('step-active');
            }
            
            // Update navigation
            updateCallbackNavigation();
        }
    };
    
    window.previousCallbackStep = function() {
        if (currentCallbackStep > 1) {
            // Hide current step
            const currentStepEl = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (currentStepEl) {
                currentStepEl.classList.add('hidden');
            }
            
            // Update step indicator
            const currentIndicator = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (currentIndicator) {
                currentIndicator.classList.remove('step-active');
                currentIndicator.classList.add('step-inactive');
            }
            
            // Show previous step
            currentCallbackStep--;
            const prevStepEl = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (prevStepEl) {
                prevStepEl.classList.remove('hidden');
            }
            
            const prevIndicator = document.getElementById(`callback-step-${currentCallbackStep}`);
            if (prevIndicator) {
                prevIndicator.classList.remove('step-completed');
                prevIndicator.classList.add('step-active');
            }
            
            // Update navigation
            updateCallbackNavigation();
        }
    };
    
    window.submitCallbackRequest = function() {
        const form = document.getElementById('callbackForm');
        if (!form) return;
        
        const formData = new FormData(form);
        
        // Validate form
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }
        
        // Show loading
        const submitText = document.getElementById('callbackSubmitText');
        const submitSpinner = document.getElementById('callbackSubmitSpinner');
        const submitBtn = document.getElementById('callbackSubmitBtn');
        
        if (submitText) submitText.classList.add('hidden');
        if (submitSpinner) submitSpinner.classList.remove('hidden');
        if (submitBtn) submitBtn.disabled = true;
        
        // Prepare callback data
        const requestData = {
            name: formData.get('name'),
            phone: formData.get('phone'),
            email: formData.get('email') || '',
            preferred_time: formData.get('preferred_time'),
            notes: formData.get('notes') || '',
            interest: callbackData.interest,
            budget: callbackData.budget,
            timing: callbackData.timing
        };
        
        // Submit callback request
        fetch('/api/callback-request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert('Заявка отправлена! Наш менеджер свяжется с вами в ближайшее время.');
                closeCallbackModal();
            } else {
                alert('Ошибка отправки заявки: ' + data.error);
                resetCallbackSubmitButton();
            }
        })
        .catch(error => {
            console.error('Callback request error:', error);
            alert('Произошла ошибка. Попробуйте еще раз.');
            resetCallbackSubmitButton();
        });
    };
    
    function resetCallbackSubmitButton() {
        const submitText = document.getElementById('callbackSubmitText');
        const submitSpinner = document.getElementById('callbackSubmitSpinner');
        const submitBtn = document.getElementById('callbackSubmitBtn');
        
        if (submitText) submitText.classList.remove('hidden');
        if (submitSpinner) submitSpinner.classList.add('hidden');
        if (submitBtn) submitBtn.disabled = false;
    }
    
    function updateCallbackNavigation() {
        const prevBtn = document.getElementById('callbackPrevBtn');
        const nextBtn = document.getElementById('callbackNextBtn');
        const submitBtn = document.getElementById('callbackSubmitBtn');
        
        // Show/hide previous button
        if (prevBtn) {
            prevBtn.style.display = currentCallbackStep > 1 ? 'block' : 'none';
        }
        
        // Show/hide next/submit buttons
        if (currentCallbackStep === totalCallbackSteps) {
            if (nextBtn) nextBtn.classList.add('hidden');
            if (submitBtn) submitBtn.classList.remove('hidden');
        } else {
            if (nextBtn) {
                nextBtn.classList.remove('hidden');
                nextBtn.disabled = true;
                nextBtn.classList.add('opacity-50');
            }
            if (submitBtn) submitBtn.classList.add('hidden');
        }
    }
    
    function showCallbackStep(step) {
        // Hide all steps
        for (let i = 1; i <= totalCallbackSteps; i++) {
            const stepEl = document.getElementById(`callback-step-${i}`);
            if (stepEl) {
                stepEl.classList.add('hidden');
            }
        }
        
        // Show current step
        const currentStepEl = document.getElementById(`callback-step-${step}`);
        if (currentStepEl) {
            currentStepEl.classList.remove('hidden');
        }
        
        // Update navigation
        updateCallbackNavigation();
    }
    
    function updateCallbackProgress(step) {
        const progress = (step / totalCallbackSteps) * 100;
        const progressBar = document.querySelector('#callback-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
        
        const stepText = document.querySelector('#callback-step-text');
        if (stepText) {
            stepText.textContent = `Шаг ${step} из ${totalCallbackSteps}`;
        }
    }
    
    // Next step handlers
    window.nextCallbackStep = function(nextStep) {
        if (nextStep <= totalCallbackSteps) {
            currentCallbackStep = nextStep;
            showCallbackStep(currentCallbackStep);
        }
    }
    
    // Previous step handler
    window.prevCallbackStep = function() {
        if (currentCallbackStep > 1) {
            currentCallbackStep--;
            showCallbackStep(currentCallbackStep);
        }
    }
    
    // Initialize first step
    showCallbackStep(1);
    
    // Handle form submission
    const callbackForm = document.getElementById('callback-form');
    if (callbackForm) {
        callbackForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            
            fetch('/api/callback-request', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Show success message and close modal
                    alert('Спасибо за заявку! Наш менеджер свяжется с вами в ближайшее время.');
                    closeCallbackModal();
                } else {
                    alert('Ошибка: ' + (data.error || 'Неизвестная ошибка'));
                }
            })
            .catch(error => {
                console.error('Error submitting callback request:', error);
                alert('Произошла ошибка при отправке заявки. Попробуйте позже.');
            });
        });
    }
}

// Close modals on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeQuizModal();
        closeCallbackModal();
    }
});