package com.amin.support.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * An isolated, endpoint-bound WSS credential. Never reuses the saved HTTPS
 * engine credential for an arbitrary WSS address, even if the operator changed
 * the WSS text field. No plaintext token is stored in preferences.
 */
public final class LiveTokenVault {
    private static final String PREFS = "amin_support_live_wss_auth";
    private static final String ALIAS = "amin_support_live_wss_aes_v1";
    private static final String ENDPOINT = "wss_endpoint";
    private static final String CIPHER = "token_cipher";
    private static final String IV = "token_iv";

    private LiveTokenVault() {}

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        KeyStore.Entry existing = store.getEntry(ALIAS, null);
        if (existing instanceof KeyStore.SecretKeyEntry)
            return ((KeyStore.SecretKeyEntry) existing).getSecretKey();
        KeyGenerator gen = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        gen.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return gen.generateKey();
    }

    public static boolean hasTokenFor(Context context, String endpoint) {
        String checked = LiveEndpointPolicy.requireWss(endpoint);
        return checked.equals(prefs(context).getString(ENDPOINT, ""))
                && prefs(context).contains(CIPHER) && prefs(context).contains(IV);
    }

    public static String token(Context context, String endpoint) throws Exception {
        if (!hasTokenFor(context, endpoint)) {
            throw new IllegalArgumentException(
                    "برای نشانی جدید کانال زنده، کلید مخصوص همان سرور را وارد کن.");
        }
        String iv = prefs(context).getString(IV, "");
        String data = prefs(context).getString(CIPHER, "");
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(
                128, Base64.decode(iv, Base64.NO_WRAP)));
        return SupportEndpoint.validateToken(
                new String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)),
                           StandardCharsets.UTF_8));
    }

    public static void save(Context context, String endpoint, String token) throws Exception {
        String checked = LiveEndpointPolicy.requireWss(endpoint);
        String secret = SupportEndpoint.validateToken(token);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] ciphertext = cipher.doFinal(secret.getBytes(StandardCharsets.UTF_8));
        if (!prefs(context).edit()
                .putString(ENDPOINT, checked)
                .putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString(CIPHER, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
                .commit()) {
            throw new IllegalStateException("ذخیره امن کلید زنده انجام نشد.");
        }
    }

    public static void clear(Context context) throws Exception {
        if (!prefs(context).edit().clear().commit())
            throw new IllegalStateException("پاک‌کردن تنظیمات WSS انجام نشد.");
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS);
    }
}
