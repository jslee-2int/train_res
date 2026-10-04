import java.util.Properties

plugins {
    id("com.chaquo.python")
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val signingProperties = Properties().apply {
    val configFile = rootProject.file("key.properties")
    if (configFile.exists()) configFile.inputStream().use { load(it) }
}

android {
    namespace = "com.jeongsu.ktx_seat_watch"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.jeongsu.ktx_seat_watch"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = 24
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (signingProperties.isNotEmpty()) {
                storeFile = file(signingProperties.getProperty("storeFile"))
                storePassword = signingProperties.getProperty("storePassword")
                keyAlias = signingProperties.getProperty("keyAlias")
                keyPassword = signingProperties.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            isShrinkResources = false
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

flutter {
    source = "../.."
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    implementation("com.google.mlkit:text-recognition:16.0.1")
}

val sharedPython = tasks.register<Copy>("syncSharedPython") {
    from("../../../ktx_watch.py")
    into(layout.buildDirectory.dir("generated/python"))
}
chaquopy {
    defaultConfig {
        version = "3.13"
        val localPython = file("../../../.venv/Scripts/python.exe")
        if (localPython.exists()) buildPython(localPython.absolutePath)
        pip {
            install("korail-mobile-api==2.4.0")
            install("cryptography==42.0.8")
        }
    }
    sourceSets.getByName("main") {
        srcDir(layout.buildDirectory.dir("generated/python"))
    }
}
tasks.configureEach {
    if (name.contains("Python") && name != "syncSharedPython") dependsOn(sharedPython)
}
