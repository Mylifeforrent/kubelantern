package com.huntai.demo.order;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicLong;

@RestController
@RequestMapping("/api/orders")
public class OrderController {

    private final AtomicLong sequence = new AtomicLong(1000);
    private final List<Map<String, Object>> orders = new CopyOnWriteArrayList<>();

    public OrderController() {
        orders.add(order("demo-order-1", "SKU-001", 2, "created"));
        orders.add(order("demo-order-2", "SKU-002", 1, "paid"));
    }

    @GetMapping
    public Map<String, Object> list() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "java-order-service");
        body.put("language", "java");
        body.put("orders", new ArrayList<>(orders));
        body.put("count", orders.size());
        body.put("checked_at", Instant.now().toString());
        return body;
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@RequestBody(required = false) Map<String, Object> payload) {
        Map<String, Object> input = payload == null ? Map.of() : payload;
        String orderId = "demo-order-" + sequence.incrementAndGet();
        Map<String, Object> created = order(
                orderId,
                String.valueOf(input.getOrDefault("sku", "SKU-DEMO")),
                Integer.parseInt(String.valueOf(input.getOrDefault("quantity", 1))),
                "created"
        );
        orders.add(created);
        return ResponseEntity.status(HttpStatus.CREATED).body(created);
    }

    @GetMapping("/boom")
    public ResponseEntity<Map<String, Object>> boom() {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(Map.of(
                "service", "java-order-service",
                "error", "injected 500 for HuntAI demo",
                "checked_at", Instant.now().toString()
        ));
    }

    @GetMapping("/slow")
    public Map<String, Object> slow(@RequestParam(defaultValue = "1500") long ms) throws InterruptedException {
        long bounded = Math.max(0, Math.min(ms, 10_000));
        Thread.sleep(bounded);
        return Map.of("service", "java-order-service", "delay_ms", bounded, "checked_at", Instant.now().toString());
    }

    private static Map<String, Object> order(String id, String sku, int quantity, String status) {
        Map<String, Object> item = new LinkedHashMap<>();
        item.put("id", id);
        item.put("sku", sku);
        item.put("quantity", quantity);
        item.put("status", status);
        item.put("created_at", Instant.now().toString());
        return item;
    }
}
