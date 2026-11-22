package com.amin.support.mobile;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.security.KeyStore;
import java.nio.charset.StandardCharsets;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Isolated Android Keystore credentials for user's own private GitHub repository. */
public final class GitHubDirectVault {
    private static final String PREFS = "amin_private_github_relay";
    private static final String ALIAS = "amin_private_github_relay_aes_v1";
    private GitHubDirectVault() {}

    private static SharedPreferences prefs(Context c) { return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE); }

    private static SecretKey key() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        KeyStore.Entry entry = ks.getEntry(ALIAS, null);
        if (entry instanceof KeyStore.SecretKeyEntry) return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
        KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        kg.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT |
                KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setKeySize(256).build());
        return kg.generateKey();
    }

    public static String repo(Context c) { return prefs(c).getString("repo", ""); }
    public static boolean available(Context c) { return prefs(c).contains("cipher") && prefs(c).contains("iv"); }

    public static String token(Context c) throws Exception {
        String iv = prefs(c).getString("iv", ""), data = prefs(c).getString("cipher", "");
        if (iv.isEmpty() || data.isEmpty()) return "";
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)));
        return new String(cipher.doFinal(Base64.decode(data, Base64.NO_WRAP)), StandardCharsets.UTF_8);
    }

    public static void save(Context c, String repo, String token) throws Exception {
        String validRepo = GitHubBridgePolicy.repo(repo);
        String validToken = GitHubBridgePolicy.token(token);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key());
        byte[] enc = cipher.doFinal(validToken.getBytes(StandardCharsets.UTF_8));
        if (!prefs(c).edit().putString("repo", validRepo)
                .putString("iv", Base64.encodeToString(cipher.getIV(), Base64.NO_WRAP))
                .putString("cipher", Base64.encodeToString(enc, Base64.NO_WRAP)).commit())
            throw new IllegalStateException("ذخیره رمزگذاری‌شده انجام نشد");
    }

    public static void clear(Context c) throws Exception {
        if (!prefs(c).edit().clear().commit()) throw new IllegalStateException("پاک کردن تنظیمات ناموفق بود");
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        if (ks.containsAlias(ALIAS)) ks.deleteEntry(ALIAS);
    }
}
