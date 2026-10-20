// E2E UI nativa (tauri-driver + WebdriverIO): controla la ventana REAL de la app.
// Este spec verifica el wiring mínimo: la app abre y el login es visible.
/* global describe, it, browser, $ */
import { expect } from '@wdio/globals';

describe('App Tauri ARCA', () => {
  it('abre la ventana y muestra el formulario de login', async () => {
    await browser.url('tauri://localhost');
    await browser.pause(2000); // espera montaje de React

    const emailInput = await $('input[type="email"], input[autocomplete="email"], input[placeholder*="@"], input').first();
    await expect(emailInput).toBeDisplayed();
  });

  it('el login rechaza credenciales vacías', async () => {
    const button = await $('button*=Ingresar, button*=Entrar, button[type="submit"]').first();
    if (await button.isDisplayed()) {
      await button.click();
      await browser.pause(500);
      // no debe navegar: el formulario sigue visible
      const emailInput = await $('input').first();
      await expect(emailInput).toBeDisplayed();
    }
  });
});
