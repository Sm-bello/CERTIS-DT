# CERTIS-DT: Mathematical and Theoretical Formulation

This document provides the complete analytical derivations and governing equations underpinning the **CERTIS-DT** testbed.

---

## 1. Structural Truth Dynamics (Cantilever Euler-Bernoulli Beam)

The transverse flexural vibration of an aerospace spar/boom arm of length $L$, mass per unit length $\mu$, and flexural rigidity $EI$ under tip aerodynamic force $F_{\text{tip}}(t)$ and distributed aero gust load $p(x,t)$ is governed by:

$$\mu \frac{\partial^2 w(x,t)}{\partial t^2} + c \frac{\partial w(x,t)}{\partial t} + EI \frac{\partial^4 w(x,t)}{\partial x^4} = p(x,t) + F_{\text{tip}}(t) \delta(x - L)$$

### 1.1 Modal Superposition
Using orthogonal modal separation:

$$w(x,t) = \sum_{n=1}^N q_n(t) \phi_n(x)$$

For a fixed-free (cantilever) beam with boundary conditions $w(0) = 0, w'(0) = 0, w''(L) = 0, w'''(L) = 0$:

$$\phi_n(x) = \cosh(\beta_n x) - \cos(\beta_n x) - \alpha_n \left[\sinh(\beta_n x) - \sin(\beta_n x)\right]$$

where $\beta_n L$ are roots of the characteristic equation $\cos(\beta L)\cosh(\beta L) + 1 = 0$, and:

$$\alpha_n = \frac{\cosh(\beta_n L) + \cos(\beta_n L)}{\sinh(\beta_n L) + \sin(\beta_n L)}$$

The natural angular frequencies are:

$$\omega_n = \beta_n^2 \sqrt{\frac{EI}{\mu}}$$

The curvature distribution $\kappa(x,t)$ and surface bending strain $\epsilon_{xx}(x,t)$ at distance $z$ from the neutral axis are:

$$\kappa(x,t) = \frac{\partial^2 w(x,t)}{\partial x^2} = \sum_{n=1}^N q_n(t) \phi''_n(x)$$

$$\epsilon_{xx}(x,t) = -z \kappa(x,t)$$

$$\sigma_{xx}(x,t) = E |\epsilon_{xx}(x,t)|$$

---

## 2. Real-Time Sparse-to-Full-Field Structural Surrogate

Let sparse strain gauge telemetry at $K$ discrete stations $x_1, \dots, x_K$ be represented by:

$$\mathbf{y}_k = \mathbf{H}_{\text{sens}} \mathbf{q}_k + \mathbf{v}_k, \quad \mathbf{v}_k \sim \mathcal{N}(\mathbf{0}, \mathbf{R})$$

where the sensor mapping matrix $\mathbf{H}_{\text{sens}} \in \mathbb{R}^{K \times M}$ is:

$$\mathbf{H}_{\text{sens}}[i, n] = -z_{\text{outer}} \phi''_n(x_i)$$

### 2.1 Precomputed Regularized Inverse Kernel
To ensure deterministic execution satisfying DO-178C Level B timing bounds, the modal amplitudes are reconstructed via Tikhonov-regularized pseudo-inverse:

$$\hat{\mathbf{q}}_k = \left(\mathbf{H}_{\text{sens}}^T \mathbf{H}_{\text{sens}} + \lambda \mathbf{I}\right)^{-1} \mathbf{H}_{\text{sens}}^T \mathbf{y}_k = \mathbf{W}_{\text{inv}} \mathbf{y}_k$$

The continuous curvature along spatial discretization nodes $\mathbf{x}_{\text{grid}} \in \mathbb{R}^{N_x}$ is computed in a single matrix-vector multiplication:

$$\hat{\boldsymbol{\kappa}}(\mathbf{x}) = \boldsymbol{\Phi}''_{\text{grid}} \hat{\mathbf{q}}_k = \left(\boldsymbol{\Phi}''_{\text{grid}} \mathbf{W}_{\text{inv}}\right) \mathbf{y}_k = \mathbf{K}_{\text{rec}} \mathbf{y}_k$$

$$\hat{\boldsymbol{\sigma}}(\mathbf{x}) = E z_{\text{outer}} |\mathbf{K}_{\text{rec}} \mathbf{y}_k|$$

Since $\mathbf{K}_{\text{rec}} \in \mathbb{R}^{N_x \times K}$ is precomputed offline, the online reconstruction complexity is $\mathcal{O}(N_x K)$, executing in $< 25\,\mu\text{s}$.

---

## 3. Physics-Informed Latent Force Model (GP-LFM) and Kalman Filter

Unknown aerodynamic loads and atmospheric turbulence $u(t)$ are modeled as a Gauss-Markov stochastic process governed by the continuous SDE:

$$\dot{u}(t) = -\gamma u(t) + w_u(t), \quad w_u(t) \sim \mathcal{GP}(0, q_u)$$

Augmenting the modal coordinates $\mathbf{x}(t) = [\mathbf{q}(t)^T, \dot{\mathbf{q}}(t)^T, u(t)]^T \in \mathbb{R}^{2M + 1}$, the exact discrete state transition matrix $\mathbf{F} \in \mathbb{R}^{(2M+1) \times (2M+1)}$ over step $\Delta t$ is:

$$\mathbf{F}_{n,n} = e^{-\zeta_n \omega_n \Delta t} \left(\cos(\omega_{d,n} \Delta t) + \frac{\zeta_n \omega_n}{\omega_{d,n}} \sin(\omega_{d,n} \Delta t)\right)$$

$$\mathbf{F}_{n, M+n} = e^{-\zeta_n \omega_n \Delta t} \frac{1}{\omega_{d,n}} \sin(\omega_{d,n} \Delta t)$$

$$\mathbf{F}_{M+n, n} = -e^{-\zeta_n \omega_n \Delta t} \frac{\omega_n^2}{\omega_{d,n}} \sin(\omega_{d,n} \Delta t)$$

$$\mathbf{F}_{M+n, M+n} = e^{-\zeta_n \omega_n \Delta t} \left(\cos(\omega_{d,n} \Delta t) - \frac{\zeta_n \omega_n}{\omega_{d,n}} \sin(\omega_{d,n} \Delta t)\right)$$

$$\mathbf{F}_{2M+1, 2M+1} = e^{-\gamma \Delta t}$$

where $\omega_{d,n} = \omega_n \sqrt{1 - \zeta_n^2}$.

---

## 4. Uncertainty Quantification & Epistemic Innovation Gating

### 4.1 Aleatory Stress Variance
Propagating the modal state error covariance $\mathbf{P}_{qq} = \mathbf{P}_{1:M, 1:M}$:

$$\sigma^2_{\text{aleatory}}(x) = (E z_{\text{outer}})^2 \cdot \boldsymbol{\phi}''(x)^T \mathbf{P}_{qq} \boldsymbol{\phi}''(x)$$

### 4.2 Epistemic Mahalanobis Distance
The Kalman filter innovation $\mathbf{r}_k = \mathbf{y}_k - \mathbf{H} \hat{\mathbf{x}}_{k|k-1}$ and innovation covariance $\mathbf{S}_k = \mathbf{H} \mathbf{P}_{k|k-1} \mathbf{H}^T + \mathbf{R}$ yield the squared Mahalanobis distance:

$$D_M^2 = \mathbf{r}_k^T \mathbf{S}_k^{-1} \mathbf{r}_k$$

Under nominal modeling, $D_M^2 \sim \chi^2_K$. The Epistemic Credibility Score $\mathcal{C}_k$ is:

$$\mathcal{C}_k = \exp\left(-\frac{\max(0, D_M^2 - K)}{2 K}\right) \in (0, 1]$$

If $\mathcal{C}_k < 0.25$ or $D_M^2 > \chi^2_{K, 0.999}$, the testbed triggers **Refusal-to-Certify**.

---

## 5. Airworthiness Margin of Safety & Exceedance Probability

Under FAR 23.303 / 25.303, the conservative 99.87% ($3\sigma$) upper credible stress is:

$$\sigma_{99}(x) = \hat{\sigma}_{\text{mean}}(x) + 3 \left(\sigma_{\text{aleatory}}(x) + \sigma_{\text{epistemic}}(x)\right)$$

The certified Margin of Safety (MS) is:

$$\text{MS}(x) = \frac{\sigma_{\text{allowable}}}{1.50 \cdot \sigma_{99}(x)} - 1.0$$

The probability of exceeding allowable structural limit is:

$$P_{\text{exceedance}}(x) = \frac{1}{2} \text{erfc}\left(\frac{\sigma_{\text{allowable}} / 1.50 - \hat{\sigma}_{\text{mean}}(x)}{\sqrt{2} \sigma_{\text{total}}(x)}\right)$$

---

## 6. Cumulative Fatigue Damage (Palmgren-Miner & Basquin)

The cumulative fatigue damage index $D \in [0, 1]$ accumulates per flight epoch according to:

$$D = \sum_{i} \frac{n_i}{N_{f,i}}$$

where cycles to failure $N_{f}$ is evaluated from the Basquin S-N formulation:

$$N_f = \left(\frac{\sigma_f'}{\sigma_a}\right)^{1/b}$$

Airworthiness threshold: $D \le 0.80$ allowable operational limit.
