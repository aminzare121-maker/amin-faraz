package com.amin.support.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyStore;
import java.security.SecureRandom;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** AndroidKeyStore-backed encrypted storage; no plaintext access keys in prefs. */
public final class TokenVault {
    private static final String PREFS = "amin_support_mobile_settings";
    private static final String ALIAS = "amin_support_mobile_scoped_token_aes";
    private static final String IV = "token_iv";
    private static final String SEALED = "token_sealed";
    private static final String ENDPOINT = "endpoint";

    private TokenVault() {}

    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        KeyStore.Entry existing = store.getEntry(ALIAS, null);
        if (existing instanceof KeyStore.SecretKeyEntry) {
            return ((KeyStore.SecretKeyEntry) existing).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return generator.generateKey();
    }

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static String endpoint(Context context) {
        return prefs(context).getString(ENDPOINT, "");
    }

    public static boolean hasToken(Context context) {
        return prefs(context).contains(SEALED) && prefs(context).contains(IV);
    }

    public static String token(Context context) throws Exception {
        String iv = prefs(context).getString(IV, "");
        String data = prefs(context).getString(SEALED, "");
        if (iv.isEmpty() || data.isEmpty()) return "";
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(
                128, Base64.decode(iv, Base64.NO_WRAP)));
        return new String(
                cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)),
                java.nio.charset.StandardCharsets.UTF_8);
    }

    public static void save(Context context, String newEndpoint, String rawToken)
            throws Exception {
        String address = SupportEndpoint.normalize(newEndpoint);
        String secret = SupportEndpoint.validateToken(rawToken);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] ciphertext = cipher.doFinal(
                secret.getBytes(java.nio.charset.StandardCharsets.UTF_8));
        boolean saved = prefs(context).edit()
                .putString(ENDPOINT, address)
                .putString(IV, Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString(SEALED, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
                .commit();
        if (!saved) throw new IllegalStateException("ذخیره تنظیمات امن انجام نشد.");
    }

    public static void clear(Context context) throws Exception {
        prefs(context).edit().clear().apply();
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) store.deleteEntry(ALIAS);
    }
}
