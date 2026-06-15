package com.vpnrouter.app.vpn

import android.net.VpnService
import android.os.ParcelFileDescriptor
import java.lang.reflect.Method
import java.lang.reflect.Proxy

class ReflectionLibboxRunner private constructor(
    private val service: VpnService,
    private val commandServer: Any,
) : SingBoxRunner {
    private var tun: ParcelFileDescriptor? = null

    override fun start(configJson: String) {
        invoke(commandServer, "start")
        val overrideOptions = newInstance("io.nekohasekai.libbox.OverrideOptions")
        invoke(commandServer, "startOrReloadService", configJson, overrideOptions)
    }

    override fun stop() {
        runCatching { invoke(commandServer, "closeService") }
        runCatching { invoke(commandServer, "close") }
        closeTun()
    }

    private fun closeTun() {
        tun?.close()
        tun = null
    }

    private fun openTun(options: Any): Int {
        val builder = service.Builder().setSession("VPN Router")
        addAddresses(builder, callIterator(options, "getInet4Address", "GetInet4Address"))
        addAddresses(builder, callIterator(options, "getInet6Address", "GetInet6Address"))
        val routeCount =
            addRoutes(builder, callIterator(options, "getInet4RouteAddress", "GetInet4RouteAddress")) +
                addRoutes(builder, callIterator(options, "getInet6RouteAddress", "GetInet6RouteAddress"))
        if (routeCount == 0) {
            builder.addRoute("0.0.0.0", 0)
            builder.addRoute("::", 0)
        }
        addDisallowedApplications(builder, callIterator(options, "getExcludePackage", "GetExcludePackage"))
        callInt(options, "getMTU", "GetMTU")?.takeIf { it > 0 }?.let(builder::setMtu)

        val descriptor = builder.establish() ?: error("Android VpnService.Builder.establish returned null")
        tun?.close()
        tun = descriptor
        return descriptor.fd
    }

    private fun addAddresses(builder: VpnService.Builder, iterator: Any?) {
        forEachIterator(iterator) { prefix ->
            val routePrefix = prefix ?: return@forEachIterator
            val address = invoke(routePrefix, "address") as? String ?: return@forEachIterator
            val bits = invoke(routePrefix, "prefix") as? Int ?: return@forEachIterator
            builder.addAddress(address, bits)
        }
    }

    private fun addRoutes(builder: VpnService.Builder, iterator: Any?): Int {
        var added = 0
        forEachIterator(iterator) { prefix ->
            val routePrefix = prefix ?: return@forEachIterator
            val address = invoke(routePrefix, "address") as? String ?: return@forEachIterator
            val bits = invoke(routePrefix, "prefix") as? Int ?: return@forEachIterator
            builder.addRoute(address, bits)
            added += 1
        }
        return added
    }

    private fun addDisallowedApplications(builder: VpnService.Builder, iterator: Any?) {
        forEachIterator(iterator) { packageName ->
            if (packageName is String && packageName.isNotBlank()) {
                runCatching { builder.addDisallowedApplication(packageName) }
            }
        }
    }

    private fun platformHandler(interfaceClass: Class<*>): Any {
        return Proxy.newProxyInstance(interfaceClass.classLoader, arrayOf(interfaceClass)) { _, method, args ->
            when (method.name) {
                "localDNSTransport", "LocalDNSTransport" -> null
                "usePlatformAutoDetectInterfaceControl", "UsePlatformAutoDetectInterfaceControl" -> true
                "autoDetectInterfaceControl", "AutoDetectInterfaceControl" -> {
                    val fd = (args?.firstOrNull() as? Number)?.toInt() ?: return@newProxyInstance null
                    if (!service.protect(fd)) error("VpnService.protect failed for fd=$fd")
                    null
                }
                "openTun", "OpenTun" -> openTun(requireNotNull(args?.firstOrNull()) { "TunOptions missing" })
                "useProcFS", "UseProcFS" -> false
                "findConnectionOwner", "FindConnectionOwner" -> null
                "startDefaultInterfaceMonitor", "StartDefaultInterfaceMonitor" -> null
                "closeDefaultInterfaceMonitor", "CloseDefaultInterfaceMonitor" -> null
                "getInterfaces", "GetInterfaces" -> emptyIteratorProxy(method.returnType)
                "underNetworkExtension", "UnderNetworkExtension" -> false
                "includeAllNetworks", "IncludeAllNetworks" -> false
                "readWIFIState", "ReadWIFIState" -> null
                "systemCertificates", "SystemCertificates" -> emptyIteratorProxy(method.returnType)
                "clearDNSCache", "ClearDNSCache" -> null
                "sendNotification", "SendNotification" -> null
                "startNeighborMonitor", "StartNeighborMonitor" -> null
                "closeNeighborMonitor", "CloseNeighborMonitor" -> null
                "registerMyInterface", "RegisterMyInterface" -> null
                "usePlatformShell", "UsePlatformShell" -> false
                "checkPlatformShell", "CheckPlatformShell" -> null
                "openShellSession", "OpenShellSession" -> null
                "lookupUser", "LookupUser" -> null
                "lookupSFTPServer", "LookupSFTPServer" -> ""
                "readSystemSSHHostKey", "ReadSystemSSHHostKey" -> ""
                "tailscaleHostname", "TailscaleHostname" -> ""
                else -> defaultReturn(method.returnType)
            }
        }
    }

    private fun commandHandler(interfaceClass: Class<*>): Any {
        return Proxy.newProxyInstance(interfaceClass.classLoader, arrayOf(interfaceClass)) { _, method, args ->
            when (method.name) {
                "serviceStop", "ServiceStop" -> {
                    closeTun()
                    null
                }
                "serviceReload", "ServiceReload" -> null
                "getSystemProxyStatus", "GetSystemProxyStatus" -> null
                "setSystemProxyEnabled", "SetSystemProxyEnabled" -> null
                "triggerNativeCrash", "TriggerNativeCrash" -> error("native crash requested by libbox")
                "writeDebugMessage", "WriteDebugMessage" -> null
                "connectSSHAgent", "ConnectSSHAgent" -> 0
                else -> defaultReturn(method.returnType)
            }
        }
    }

    companion object {
        fun createOrNull(service: VpnService): ReflectionLibboxRunner? {
            return runCatching {
                val platformInterfaceClass = Class.forName("io.nekohasekai.libbox.PlatformInterface")
                val commandHandlerClass = Class.forName("io.nekohasekai.libbox.CommandServerHandler")
                val commandServerClass = Class.forName("io.nekohasekai.libbox.CommandServer")
                val runner = ReflectionLibboxRunner(
                    service = service,
                    commandServer = commandServerClass.getConstructor(commandHandlerClass, platformInterfaceClass)
                        .newInstance(
                            ProxyPlaceholder.commandHandler(commandHandlerClass),
                            ProxyPlaceholder.platformHandler(service, platformInterfaceClass),
                        ),
                )
                ProxyPlaceholder.bind(runner)
                runner
            }.getOrNull()
        }
    }

    private object ProxyPlaceholder {
        private var runner: ReflectionLibboxRunner? = null

        fun bind(value: ReflectionLibboxRunner) {
            runner = value
        }

        fun platformHandler(service: VpnService, interfaceClass: Class<*>): Any {
            val bootstrapRunner = ReflectionLibboxRunner(service, commandServer = Any())
            return Proxy.newProxyInstance(interfaceClass.classLoader, arrayOf(interfaceClass)) { _, method, args ->
                (runner ?: bootstrapRunner).platformHandler(interfaceClass)
                    .let { Proxy.getInvocationHandler(it).invoke(it, method, args) }
            }
        }

        fun commandHandler(interfaceClass: Class<*>): Any {
            return Proxy.newProxyInstance(interfaceClass.classLoader, arrayOf(interfaceClass)) { _, method, args ->
                val activeRunner = runner ?: return@newProxyInstance defaultReturn(method.returnType)
                activeRunner.commandHandler(interfaceClass)
                    .let { Proxy.getInvocationHandler(it).invoke(it, method, args) }
            }
        }
    }
}

private fun callIterator(target: Any, vararg names: String): Any? {
    return names.firstNotNullOfOrNull { name ->
        runCatching { invoke(target, name) }.getOrNull()
    }
}

private fun callInt(target: Any, vararg names: String): Int? {
    return names.firstNotNullOfOrNull { name ->
        runCatching { invoke(target, name) as? Int }.getOrNull()
    }
}

private fun forEachIterator(iterator: Any?, block: (Any?) -> Unit) {
    if (iterator == null) return
    while (callBoolean(iterator, "hasNext", "HasNext") == true) {
        block(callAny(iterator, "next", "Next"))
    }
}

private fun callBoolean(target: Any, vararg names: String): Boolean? {
    return names.firstNotNullOfOrNull { name ->
        runCatching { invoke(target, name) as? Boolean }.getOrNull()
    }
}

private fun callAny(target: Any, vararg names: String): Any? {
    return names.firstNotNullOfOrNull { name ->
        runCatching { invoke(target, name) }.getOrNull()
    }
}

private fun emptyIteratorProxy(interfaceClass: Class<*>): Any? {
    if (!interfaceClass.isInterface) return null
    return Proxy.newProxyInstance(interfaceClass.classLoader, arrayOf(interfaceClass)) { _, method, _ ->
        when (method.name) {
            "hasNext", "HasNext" -> false
            "next", "Next" -> null
            else -> defaultReturn(method.returnType)
        }
    }
}

private fun newInstance(className: String): Any {
    return Class.forName(className).getConstructor().newInstance()
}

private fun invoke(target: Any, methodName: String, vararg args: Any?): Any? {
    val method = target.javaClass.methods.firstOrNull { method ->
        method.name == methodName && method.parameterTypes.size == args.size
    } ?: error("method $methodName/${args.size} not found on ${target.javaClass.name}")
    return method.invoke(target, *args)
}

private fun defaultReturn(type: Class<*>): Any? {
    return when (type) {
        java.lang.Boolean.TYPE -> false
        java.lang.Byte.TYPE -> 0.toByte()
        java.lang.Short.TYPE -> 0.toShort()
        java.lang.Integer.TYPE -> 0
        java.lang.Long.TYPE -> 0L
        java.lang.Float.TYPE -> 0f
        java.lang.Double.TYPE -> 0.0
        java.lang.Character.TYPE -> 0.toChar()
        java.lang.Void.TYPE -> null
        else -> null
    }
}
